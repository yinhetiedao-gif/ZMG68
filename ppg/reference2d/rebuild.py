from __future__ import annotations

"""EditablePatternDocument 的确定性 Rebuild 内核。

这里不读取 Raster，也不调用 LLM。检测阶段留下的 Base Elements 与数学拟合的
Generator 参数共同产生新的基础状态，之后依次应用 Modifier Stack 和 Element
Overrides。每个元素 ID 保持稳定，因此局部编辑不会被重新生成覆盖。
"""

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .editable_document import EditableElement, EditablePatternDocument


def _number(values: dict[str, Any], name: str, fallback: float) -> float:
    try:
        return float(values.get(name, fallback))
    except (TypeError, ValueError):
        return fallback


def _bindings(document: "EditablePatternDocument") -> dict[str, dict[str, float]]:
    raw = document.generator.get("bindings", {})
    if isinstance(raw, dict):
        return {str(key): dict(value) for key, value in raw.items() if isinstance(value, dict)}
    return {}


def _parametric_seed(document: "EditablePatternDocument", element: "EditableElement") -> "EditableElement":
    item = element.clone()
    if document.mode != "parametric":
        return item
    params = document.generator.get("parameters", {})
    if not isinstance(params, dict):
        return item
    binding = _bindings(document).get(item.id, {})
    base = str(document.generator.get("base", ""))
    if base in {"regular_grid", "dot_matrix", "halftone"} and binding:
        origin_x, origin_y = _number(params, "origin_x", 0.0), _number(params, "origin_y", 0.0)
        spacing_x, spacing_y = _number(params, "spacing_x", 1.0), _number(params, "spacing_y", 1.0)
        scale_x, scale_y = _number(params, "scale_x", 1.0), _number(params, "scale_y", 1.0)
        item.x = origin_x + _number(binding, "u", 0.0) * spacing_x * scale_x
        item.y = origin_y + _number(binding, "v", 0.0) * spacing_y * scale_y
    elif base == "radial" and binding:
        center_x, center_y = _number(params, "center_x", 50.0), _number(params, "center_y", 50.0)
        radius_scale = _number(params, "radius_scale", 1.0)
        angle = math.radians(_number(binding, "angle", 0.0) + _number(params, "rotation", 0.0))
        radius = _number(binding, "radius", 0.0) * radius_scale
        item.x, item.y = center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius
    return item


def _normalized(item: "EditableElement", axis: str) -> float:
    return max(0.0, min(1.0, item.x / 100.0 if axis.lower() == "x" else item.y / 100.0))


def _apply_modifiers(document: "EditablePatternDocument", items: list["EditableElement"]) -> None:
    for modifier in document.modifiers:
        if not isinstance(modifier, dict):
            continue
        params = modifier.get("parameters", {})
        if not isinstance(params, dict) or not bool(params.get("enabled", False)):
            continue
        name = str(modifier.get("name", modifier.get("type", ""))).lower()
        if name in {"sizegradient", "sizefield"}:
            axis, strength = str(params.get("axis", "y")), _number(params, "strength", 0.0)
            for item in items:
                factor = max(0.05, 1.0 + strength * (_normalized(item, axis) - 0.5))
                item.width *= factor; item.height *= factor; item.radius *= factor
        elif name in {"rotationfield", "rotation"}:
            axis, strength = str(params.get("axis", "y")), _number(params, "strength", 0.0)
            for item in items:
                item.rotation += strength * (_normalized(item, axis) - 0.5)
        elif name in {"simplewarp", "warpfield"}:
            amplitude = _number(params, "amplitude", 0.0)
            frequency = max(0.001, _number(params, "frequency", 1.0))
            axis = str(params.get("axis", "x")).lower()
            for item in items:
                coordinate = item.y if axis == "x" else item.x
                displacement = amplitude * math.sin(math.tau * frequency * coordinate / 100.0)
                if axis == "x":
                    item.x += displacement
                else:
                    item.y += displacement
        elif name in {"mask", "shapemask"}:
            shape = str(params.get("shape", "circle")).lower()
            feather = max(0.0, _number(params, "feather", 0.0))
            center_x, center_y = _number(params, "center_x", 50.0), _number(params, "center_y", 50.0)
            radius = max(0.001, _number(params, "radius", 50.0))
            for item in items:
                if shape == "circle":
                    item.enabled = math.hypot(item.x - center_x, item.y - center_y) <= radius + feather
        elif name in {"densityfield", "density"}:
            # Density 不删除真实元素；低密度只降低可见度，避免一次规则修改丢失对象。
            axis, strength = str(params.get("axis", "y")), max(0.0, min(1.0, _number(params, "strength", 0.0)))
            for item in items:
                item.opacity *= max(0.0, min(1.0, 1.0 - strength * (1.0 - _normalized(item, axis))))


def _apply_overrides(document: "EditablePatternDocument", items: list["EditableElement"]) -> list["EditableElement"]:
    materialized: list["EditableElement"] = []
    for item in items:
        override = document.overrides.get(item.id, {})
        if not isinstance(override, dict) or override.get("deleted", False):
            continue
        item.x += _number(override, "offset_x", 0.0); item.y += _number(override, "offset_y", 0.0)
        size_scale = max(0.01, _number(override, "size_scale", 1.0))
        item.width *= size_scale; item.height *= size_scale; item.radius *= size_scale
        item.rotation += _number(override, "rotation_offset", 0.0)
        if "enabled" in override:
            item.enabled = bool(override["enabled"])
        if "opacity" in override:
            item.opacity = max(0.0, min(1.0, _number(override, "opacity", item.opacity)))
        if "group_id" in override:
            item.group_id = str(override["group_id"])
        materialized.append(item)
    return materialized


def rebuild_document(document: "EditablePatternDocument") -> list["EditableElement"]:
    """重建当前可编辑元素；返回值和 ``document.elements`` 是同一物化结果。"""
    seeds = [item.clone() for item in document.base_elements + document.added_elements]
    materialized = [_parametric_seed(document, item) for item in seeds]
    _apply_modifiers(document, materialized)
    document.elements = _apply_overrides(document, materialized)
    valid_ids = {item.id for item in document.elements}
    document.selected_ids = [item_id for item_id in document.selected_ids if item_id in valid_ids]
    document.metadata["last_rebuild"] = {
        "mode": document.mode,
        "element_count": len(document.elements),
        "source": "base_generator+modifier_stack+local_overrides",
    }
    return document.elements
