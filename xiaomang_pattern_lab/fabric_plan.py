"""F2 regular placement and immutable derived instance plan."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Any, Mapping

from .fabric_cells import UNIT_CELL_REGISTRY, UnitCellDefinition


MAX_PREVIEW_INSTANCES = 5000


def _preview_indices(total: int):
    """Select up to the preview cap without changing the underlying design."""
    if total <= MAX_PREVIEW_INSTANCES:
        return range(total)
    last = total - 1
    denominator = MAX_PREVIEW_INSTANCES - 1
    return (index * last // denominator for index in range(MAX_PREVIEW_INSTANCES))


@lru_cache(maxsize=64)
def _preview_prototype(cell: UnitCellDefinition):
    # Mesh is read-only in a FabricInstancePlan. Do not mutate this cached mesh.
    return UNIT_CELL_REGISTRY.create(cell)


@dataclass(frozen=True)
class RegularPlacement:
    spacing_x_mm: float
    spacing_y_mm: float

    def __post_init__(self) -> None:
        for value, key in ((self.spacing_x_mm, "spacing_x_mm"),
                           (self.spacing_y_mm, "spacing_y_mm")):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"布点 {key} 必须是大于 0 的有限毫米数值。")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "RegularPlacement":
        values = []
        for key in ("spacing_x_mm", "spacing_y_mm"):
            value = raw.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"布点 {key} 必须是大于 0 的有限毫米数值。")
            values.append(float(value))
        return cls(*values)


@dataclass(frozen=True)
class FabricInstance:
    id: str
    x_mm: float
    y_mm: float
    z_mm: float
    cell_type: str
    height_mm: float
    rotation_deg: float = 0.0
    scale: float = 1.0
    source_id: str | None = None
    final_geometry_id: str | None = None
    scale_x: float = 1.0
    scale_y: float = 1.0
    enabled: bool = True
    base_width_mm: float | None = None
    base_depth_mm: float | None = None
    base_height_mm: float | None = None
    cell_width_mm: float | None = None
    cell_depth_mm: float | None = None


@dataclass(frozen=True)
class FabricPlacementPoint:
    final_geometry_id: str
    source_id: str | None
    x_mm: float
    y_mm: float
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_deg: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class FabricInstancePlan:
    cell: UnitCellDefinition
    instances: tuple[FabricInstance, ...]
    bounds_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    prototype: Any
    total_count: int = 0
    skipped_count: int = 0

    @property
    def count(self) -> int:
        return len(self.instances)

    def preview_payload(self) -> dict[str, Any]:
        return {"schema_version": "1.0", "kind": "fabric_instance_preview",
                "cell_type": self.cell.type, "count": self.count,
                "active_count": sum(item.enabled for item in self.instances),
                "total_count": self.total_count or self.count,
                "skipped_count": self.skipped_count,
                "preview_simplified": (self.total_count or self.count) > self.count,
                "bounds_mm": self.bounds_mm,
                "prototype": {"vertices": self.prototype.vertices.tolist(),
                              "faces": self.prototype.faces.tolist()},
                "instances": [{"id": item.id, "x_mm": item.x_mm, "y_mm": item.y_mm,
                               "z_mm": item.z_mm, "rotation_deg": item.rotation_deg,
                               "scale": item.scale, "scale_x": item.scale_x,
                               "scale_y": item.scale_y, "enabled": item.enabled,
                               "height_mm": item.height_mm, "cell_type": item.cell_type,
                               "base_width_mm": item.base_width_mm,
                               "base_depth_mm": item.base_depth_mm,
                               "base_height_mm": item.base_height_mm,
                               "cell_width_mm": item.cell_width_mm,
                               "cell_depth_mm": item.cell_depth_mm,
                               "cell_height_mm": item.height_mm,
                               "source_id": item.source_id,
                               "final_geometry_id": item.final_geometry_id}
                              for item in self.instances],
                "manufacturing_status": "preview_only_not_in_stl"}


class FabricPlanner:
    def plan(self, base_bounds_mm: tuple[float, float, float, float], base_top_z: float,
             cell: UnitCellDefinition, placement: RegularPlacement) -> FabricInstancePlan:
        if len(base_bounds_mm) != 4 or any(not math.isfinite(value) for value in base_bounds_mm):
            raise ValueError("Fabric Base 范围必须是有限毫米坐标。")
        left, bottom, right, top = base_bounds_mm
        if right <= left or top <= bottom or not math.isfinite(base_top_z) or base_top_z <= 0:
            raise ValueError("Fabric Base 范围或顶部高度无效。")
        columns = math.floor((right - left) / placement.spacing_x_mm + 1e-9)
        rows = math.floor((top - bottom) / placement.spacing_y_mm + 1e-9)
        if columns < 1 or rows < 1:
            raise ValueError("布点间距大于基底尺寸，无法生成 Unit Cell。")
        prototype = _preview_prototype(cell)
        total = columns * rows
        instances = tuple(FabricInstance(f"fabric:r{index // columns}:c{index % columns}",
                          left + (index % columns + .5) * placement.spacing_x_mm,
                          bottom + (index // columns + .5) * placement.spacing_y_mm, base_top_z,
                          cell.type, cell.height_mm,
                          base_width_mm=cell.width_mm, base_depth_mm=cell.depth_mm,
                          base_height_mm=cell.height_mm, cell_width_mm=cell.width_mm,
                          cell_depth_mm=cell.depth_mm)
                          for index in _preview_indices(total))
        bounds = ((left + placement.spacing_x_mm / 2 - cell.width_mm / 2,
                   bottom + placement.spacing_y_mm / 2 - cell.depth_mm / 2, base_top_z),
                  (left + (columns - .5) * placement.spacing_x_mm + cell.width_mm / 2,
                   bottom + (rows - .5) * placement.spacing_y_mm + cell.depth_mm / 2,
                   base_top_z + cell.height_mm))
        return FabricInstancePlan(cell, instances, bounds, prototype, total_count=total)

    def plan_points(self, points: list[FabricPlacementPoint], base_top_z: float,
                    cell: UnitCellDefinition, *, follow_pattern_size: bool = True) -> FabricInstancePlan:
        if not math.isfinite(base_top_z) or base_top_z <= 0:
            raise ValueError("Fabric Base 顶部高度无效。")
        valid = [point for point in points
                 if point.enabled and isinstance(point.final_geometry_id, str) and point.final_geometry_id
                 and all(type(value) in (int, float) and math.isfinite(value)
                         for value in (point.x_mm, point.y_mm, point.scale_x,
                                       point.scale_y, point.rotation_deg))
                 and point.scale_x > 0 and point.scale_y > 0]
        if not valid:
            raise ValueError("当前最终二维几何没有可用于布点的有效元素。")
        total = len(valid)
        instances = tuple(FabricInstance(f"fabric:final:{point.final_geometry_id}",
                          point.x_mm, point.y_mm, base_top_z, cell.type, cell.height_mm,
                          rotation_deg=point.rotation_deg, source_id=point.source_id,
                          final_geometry_id=point.final_geometry_id,
                          scale_x=point.scale_x if follow_pattern_size else 1.0,
                          scale_y=point.scale_y if follow_pattern_size else 1.0,
                          base_width_mm=cell.width_mm, base_depth_mm=cell.depth_mm,
                          base_height_mm=cell.height_mm,
                          cell_width_mm=cell.width_mm * (point.scale_x if follow_pattern_size else 1.0),
                          cell_depth_mm=cell.depth_mm * (point.scale_y if follow_pattern_size else 1.0))
                          for point in (valid[index] for index in _preview_indices(total)))
        extents = []
        for point in valid:
            angle = math.radians(point.rotation_deg)
            half_width = cell.width_mm * (point.scale_x if follow_pattern_size else 1.0) / 2
            half_depth = cell.depth_mm * (point.scale_y if follow_pattern_size else 1.0) / 2
            dx = abs(math.cos(angle)) * half_width + abs(math.sin(angle)) * half_depth
            dy = abs(math.sin(angle)) * half_width + abs(math.cos(angle)) * half_depth
            extents.append((point.x_mm - dx, point.y_mm - dy,
                            point.x_mm + dx, point.y_mm + dy))
        bounds = ((min(item[0] for item in extents), min(item[1] for item in extents), base_top_z),
                  (max(item[2] for item in extents), max(item[3] for item in extents),
                   base_top_z + cell.height_mm))
        return FabricInstancePlan(cell, instances, bounds, _preview_prototype(cell),
                                  total_count=total, skipped_count=len(points) - total)


def plan_from_fabric_config(config, manufacturing_bounds_mm):
    raw = config.get("unit_cell")
    if raw is None:
        return None
    placement_raw = config.get("placement")
    if not isinstance(raw, Mapping) or not isinstance(placement_raw, Mapping):
        raise ValueError("Unit Cell 需要定义单元类型和规则布点。")
    base = config["base"]
    margin = float(base.get("margin_mm", 0))
    left, bottom, right, top = manufacturing_bounds_mm
    return FabricPlanner().plan((left - margin, bottom - margin, right + margin, top + margin),
                                float(base["thickness_mm"]), UnitCellDefinition.from_mapping(raw),
                                RegularPlacement.from_mapping(placement_raw))
