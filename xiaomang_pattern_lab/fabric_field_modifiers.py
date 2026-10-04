"""Read-only Shared Field consumers for Fabric preview instances.

The placement plan is derived from Final Geometry first. These modifiers only
change that plan; they never edit PatternDocument or create manufacturing mesh.
"""
from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import math
from typing import Any, Mapping

from ppg.foundation.models import Element

from .fabric_plan import FabricInstancePlan
from .shared_fields import CompositeField, FieldContext, FieldRegistry, ImageField


MODIFIER_TYPES = ("height", "scale", "density", "orientation")
ALLOWED_FIELD_TYPES = frozenset(("constant", "linear", "wave", "ring", "stripe",
                                 "checker", "spiral", "noise", "composite", "image", "distance"))


def _number(raw: Mapping[str, Any], key: str, *, positive: bool = False,
            unit_interval: bool = False) -> float:
    value = raw.get(key)
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Fabric {key} 必须是有限数字。")
    if positive and value <= 0:
        raise ValueError(f"Fabric {key} 必须大于 0。")
    if unit_interval and not 0 <= value <= 1:
        raise ValueError(f"Fabric {key} 必须在 0～1 之间。")
    return float(value)


def _check_field(registry: FieldRegistry, field_id: str,
                 seen: frozenset[str] = frozenset()) -> None:
    if field_id in seen:
        raise ValueError("Fabric 组合场存在循环引用。")
    field = registry.get(field_id)
    kind = field.to_dict()["type"]
    if kind not in ALLOWED_FIELD_TYPES:
        raise ValueError(f"Fabric 预览暂不支持 {kind} 参数场。")
    if isinstance(field, ImageField) and not field.available():
        raise ValueError("图片场源图片失效，请重新上传或恢复本地草稿。")
    if isinstance(field, ImageField):
        field.prepare_sampling()
    if isinstance(field, CompositeField):
        # Missing composite inputs retain the existing FieldRegistry neutral
        # fallback. Present inputs must not smuggle in an unsupported field.
        for child in (field.input_a_field_id, field.input_b_field_id):
            try:
                registry.get(child)
            except ValueError:
                continue
            _check_field(registry, child, seen | {field_id})


def apply_fabric_field_modifiers(plan: FabricInstancePlan, document,
                                 raw: Any) -> FabricInstancePlan:
    """Evaluate each referenced field once per placement point in world mm."""
    if raw is None or raw == {}:
        return plan
    if not isinstance(raw, Mapping) or any(kind not in MODIFIER_TYPES for kind in raw):
        raise ValueError("Fabric Field Modifier 配置无效。")
    active: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for kind in MODIFIER_TYPES:
        item = raw.get(kind)
        if item is None:
            continue
        if not isinstance(item, Mapping) or type(item.get("enabled")) is not bool:
            raise ValueError(f"Fabric {kind} 配置无效。")
        if not item["enabled"]:
            continue
        field_id = item.get("field_id")
        if not isinstance(field_id, str) or not field_id:
            raise ValueError(f"Fabric {kind} 缺少参数场绑定。")
        if kind == "height":
            lo, hi = _number(item, "min_height_mm", positive=True), _number(item, "max_height_mm", positive=True)
        elif kind == "scale":
            lo, hi = _number(item, "min_scale", positive=True), _number(item, "max_scale", positive=True)
        elif kind == "orientation":
            lo, hi = _number(item, "min_angle_deg"), _number(item, "max_angle_deg")
            if item.get("direction_mode", "value") not in ("value", "gradient"):
                raise ValueError("Fabric 方向模式无效。")
            if item.get("alignment", "normal") not in ("normal", "tangent"):
                raise ValueError("Fabric 梯度对齐方式无效。")
            _number({"angle_offset_deg": item.get("angle_offset_deg", 0)}, "angle_offset_deg")
        else:
            _number(item, "threshold", unit_interval=True)
            lo = hi = 0.0
        if lo > hi:
            raise ValueError(f"Fabric {kind} 最小值不能大于最大值。")
        active[kind] = (field_id, item)
    if not active or not plan.instances:
        return plan

    fields = deepcopy(document.fields)
    factor = document.canvas.mm_per_unit or 1.0
    for field in fields:
        if field.get("type") in ("image", "distance"):
            parameters = field.setdefault("parameters", {})
            if not parameters.get("image_path"):
                parameters["image_path"] = document.reference.source_path
            if parameters.get("sample_bounds") is not None:
                parameters["sample_bounds"] = [value * factor for value in parameters["sample_bounds"]]
    registry = FieldRegistry.from_list(fields)
    for field_id, _ in active.values():
        _check_field(registry, field_id)
    elements = [Element(item.id, "rect", item.x_mm, item.y_mm, 1.0, 1.0)
                for item in plan.instances]
    context = FieldContext.from_elements(elements)
    values = {field_id: tuple(registry.evaluate(field_id, item, context) for item in elements)
              for field_id in {field_id for field_id, _ in active.values()}}
    directions = None
    if "orientation" in active and active["orientation"][1].get("direction_mode", "value") == "gradient":
        from .field_gradient import gradient_angles
        directions = gradient_angles(registry, active["orientation"][0], elements, context)
    derived = []
    for index, item in enumerate(plan.instances):
        height, scale, rotation, enabled = item.height_mm, item.scale, item.rotation_deg, item.enabled
        if "height" in active:
            field_id, config = active["height"]
            height = config["min_height_mm"] + (config["max_height_mm"] - config["min_height_mm"]) * values[field_id][index]
        if "scale" in active:
            field_id, config = active["scale"]
            scale *= config["min_scale"] + (config["max_scale"] - config["min_scale"]) * values[field_id][index]
        if "orientation" in active:
            field_id, config = active["orientation"]
            if directions is None:
                rotation += config["min_angle_deg"] + (config["max_angle_deg"] - config["min_angle_deg"]) * values[field_id][index]
                rotation += config.get("angle_offset_deg", 0)
            elif directions[index] is not None:
                rotation += directions[index] + (90 if config.get("alignment", "normal") == "tangent" else 0) + config.get("angle_offset_deg", 0)
        if "density" in active:
            field_id, config = active["density"]
            enabled = enabled and values[field_id][index] >= config["threshold"]
        derived.append(replace(item, height_mm=height, scale=scale,
                               cell_width_mm=plan.cell.width_mm * item.scale_x * scale,
                               cell_depth_mm=plan.cell.depth_mm * item.scale_y * scale,
                               rotation_deg=rotation, enabled=enabled))
    visible = [item for item in derived if item.enabled]
    if visible:
        extents = []
        for item in visible:
            angle = math.radians(item.rotation_deg)
            half_width = item.cell_width_mm / 2
            half_depth = item.cell_depth_mm / 2
            dx = abs(math.cos(angle)) * half_width + abs(math.sin(angle)) * half_depth
            dy = abs(math.sin(angle)) * half_width + abs(math.cos(angle)) * half_depth
            extents.append((item.x_mm - dx, item.y_mm - dy,
                            item.x_mm + dx, item.y_mm + dy))
        bounds = ((min(part[0] for part in extents), min(part[1] for part in extents),
                   min(item.z_mm for item in visible)),
                  (max(part[2] for part in extents), max(part[3] for part in extents),
                   max(item.z_mm + item.height_mm for item in visible)))
    else:
        bounds = plan.bounds_mm
    return replace(plan, instances=tuple(derived), bounds_mm=bounds)
