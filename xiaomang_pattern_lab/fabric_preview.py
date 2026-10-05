"""Read-only, non-manufacturing Fabric design preview.

No extrusion, Boolean, mesh validation, STL, or GLB is performed here. The
returned prototype is shared by all instance transforms in the browser.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
from hashlib import sha256
import json
import math
from threading import Lock
from time import perf_counter
from typing import Any

from .contracts.v1 import PatternDocumentDTO, final_geometry
from .evaluation import parametric_model_from_document
from .fabric_base import FabricConfig
from .fabric_cells import UnitCellDefinition
from .fabric_field_modifiers import apply_fabric_field_modifiers
from .fabric_plan import FabricPlacementPoint, FabricInstancePlan, FabricPlanner, RegularPlacement
from .placement_assignment import PlacementAssignmentState
from .shared_modifiers import SharedModifierStack


class FabricPreviewCache:
    def __init__(self, capacity: int = 16) -> None:
        self.capacity = capacity
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)


def preview_key(dto: PatternDocumentDTO) -> str:
    # Hash the full document, not only revision: callers cannot reuse a stale
    # plan by accidentally submitting changed content with the same revision.
    encoded = json.dumps(dto.to_dict(), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _reference_dimensions_mm(document) -> dict[str, tuple[float, float]]:
    """Read the evaluator's stable pre-modifier source, never the Canvas frame."""
    model = parametric_model_from_document(document)
    stack = SharedModifierStack.from_document(document)
    if model is not None:
        source = model.generate()
    else:
        placement_raw = document.metadata.get("xiaomang_pattern_lab.placement_assignment")
        if isinstance(placement_raw, dict) and placement_raw.get("enabled"):
            state = PlacementAssignmentState.from_dict(placement_raw)
            source = (state.source_snapshot() if state.source_elements else
                      stack.source_snapshot() if stack and stack.source_elements else document.elements)
        else:
            source = stack.source_snapshot() if stack and stack.source_elements else document.elements
    factor = document.canvas.mm_per_unit if document.canvas.mm_per_unit is not None else 1.0
    return {item.id: (item.width * factor, item.height * factor) for item in source
            if item.width > 0 and item.height > 0}


@dataclass(frozen=True)
class FabricDesignInput:
    config: FabricConfig
    plan: FabricInstancePlan | None
    design_bounds_mm: tuple[float, float, float, float]
    metadata: dict[str, Any]


def build_fabric_design(document, dto: PatternDocumentDTO, *, preview_limit: bool = True) -> FabricDesignInput:
    started = perf_counter()
    raw = document.metadata.get("fabric_config")
    if not isinstance(raw, dict):
        raise ValueError("请先配置 Fabric Base。")
    config = FabricConfig.from_mapping(raw)
    cell_raw = raw.get("unit_cell")
    cell = UnitCellDefinition.from_mapping(cell_raw) if isinstance(cell_raw, dict) else None
    size_mode = cell_raw.get("size_mode", "follow_pattern") if isinstance(cell_raw, dict) else "follow_pattern"
    if size_mode not in ("fixed", "follow_pattern"):
        raise ValueError("不支持的 Unit Cell 尺寸模式。")
    placement = raw.get("placement")
    if cell is not None and not isinstance(placement, dict):
        raise ValueError("Fabric 布点配置缺失。")
    if cell is None and raw.get("field_modifiers"):
        raise ValueError("请先配置 Unit Cell，再启用 Fabric Field Modifier。")
    mode = placement.get("mode", "area_fill") if isinstance(placement, dict) else "area_fill"
    if mode not in ("area_fill", "pattern_points"):
        raise ValueError("不支持的 Fabric 布点方式。")
    geometry, bounds = final_geometry(document)
    evaluated_at = perf_counter()
    if not bounds or bounds["width"] <= 0 or bounds["height"] <= 0:
        raise ValueError("当前二维设计没有有效的 Fabric 范围。")
    left, bottom, right, top = (bounds["min_x"], bounds["min_y"], bounds["max_x"], bounds["max_y"])
    margin = config.base.margin_mm
    base_bounds = (left - margin, bottom - margin, right + margin, top + margin)
    if cell is None:
        plan = None
    elif mode == "area_fill":
        plan = FabricPlanner().plan(base_bounds, config.base.thickness_mm, cell,
                                    RegularPlacement.from_mapping(placement), preview_limit=preview_limit)
    else:
        reference_sizes = _reference_dimensions_mm(document)
        points = []
        unmatched_reference_count = 0
        for item in geometry:
            final_id = item.get("id")
            reference = reference_sizes.get(final_id)
            if reference is None:
                # Position/rotation remain authoritative. Without a stable
                # reference size, unity is the only non-invented scale.
                unmatched_reference_count += 1
            width, height = item.get("width"), item.get("height")
            if not (isinstance(width, (int, float)) and isinstance(height, (int, float))
                    and width > 0 and height > 0):
                continue
            points.append(FabricPlacementPoint(
                final_geometry_id=final_id,
                source_id=final_id if reference is not None else None,
                x_mm=item.get("x"), y_mm=item.get("y"),
                scale_x=width / reference[0] if reference else 1.0,
                scale_y=height / reference[1] if reference else 1.0,
                rotation_deg=item.get("rotation", 0.0),
            ))
        plan = FabricPlanner().plan_points(points, config.base.thickness_mm, cell,
                                           follow_pattern_size=size_mode == "follow_pattern", preview_limit=preview_limit)
    if plan is not None:
        plan = apply_fabric_field_modifiers(plan, document, raw.get("field_modifiers"))
    planned_at = perf_counter()
    metadata = {"document_id": dto.document_id, "document_revision": dto.document_revision,
                    "placement_mode": mode, "element_count": len(geometry),
                    "unit_size_mode": size_mode,
                    "unmatched_reference_count": unmatched_reference_count if mode == "pattern_points" else 0,
                    "base_preview": {"type": config.base.type, "bounds_mm": base_bounds,
                                     "thickness_mm": config.base.thickness_mm,
                                     "spacing_x_mm": config.base.spacing_x_mm,
                                     "spacing_y_mm": config.base.spacing_y_mm,
                                     "line_width_mm": config.base.line_width_mm},
                    "timings_ms": {"evaluate": round((evaluated_at - started) * 1000, 3),
                                   "plan_and_prototype": round((planned_at - evaluated_at) * 1000, 3)}}
    return FabricDesignInput(config, plan, (left, bottom, right, top), metadata)


def build_fabric_preview(document, dto: PatternDocumentDTO) -> dict[str, Any]:
    design = build_fabric_design(document, dto)
    plan = design.plan
    payload = plan.preview_payload() if plan else {
        "schema_version": "1.0", "kind": "fabric_instance_preview", "cell_type": None,
        "count": 0, "total_count": 0, "skipped_count": 0, "preview_simplified": False,
        "active_count": 0,
        "prototype": None, "instances": [], "manufacturing_status": "preview_only_not_in_stl"}
    payload.update(design.metadata)
    # Preview API has no manufacturing_result_id. It is intentionally not an
    # exportable, validated manufacturing result.
    payload["preview_id"] = preview_key(dto)
    payload["cache_hit"] = False
    serialized_at = perf_counter()
    json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    payload["timings_ms"]["serialization"] = round((perf_counter() - serialized_at) * 1000, 3)
    return payload
