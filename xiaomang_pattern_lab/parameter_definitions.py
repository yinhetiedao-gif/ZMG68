"""UI-independent parameter metadata for existing layout/field/modifier models.

This catalog describes editable values; it does not evaluate geometry or create
new model types.  Python remains the authority for bounds and option validity.
"""
from __future__ import annotations

import math
from typing import Any


def _p(id: str, label: str, type: str, default: Any, *, min: float | None = None,
       max: float | None = None, step: float | None = None, unit: str = "",
       options: list[dict[str, str]] | None = None, description: str = "",
       advanced: bool = False) -> dict[str, Any]:
    return {"id": id, "label": label, "type": type, "default": default,
            "value": default, "min": min, "max": max, "step": step,
            "unit": unit, "options": options or [], "description": description,
            "advanced": advanced}


def _coord(id: str, label: str, default: float = 0.0) -> dict[str, Any]:
    return _p(id, label, "number", default, min=-10000, max=10000, step=0.1, unit="mm")


def _size(id: str, label: str, default: float) -> dict[str, Any]:
    return _p(id, label, "number", default, min=0.01, max=10000, step=0.1, unit="mm")


def parameter_definitions() -> dict[str, Any]:
    """Return a fresh, JSON-safe catalog; callers cannot mutate the source."""
    angle = lambda id, label, default=0.0: _p(id, label, "number", default, min=-360, max=360, step=1, unit="°")
    invert = _p("invert", "反转", "boolean", False)
    return {"schema_version": "1.0", "units": "mm", "definitions": {
        "layout": {
            "free": {"label": "自由布局", "parameters": []},
            "grid": {"label": "规则矩阵", "parameters": [
                _p("rows", "行数", "integer", 12, min=1, max=500, step=1),
                _p("columns", "列数", "integer", 12, min=1, max=500, step=1),
                _size("spacing_x", "水平间距", 20), _size("spacing_y", "垂直间距", 20),
                _size("element_width", "单元宽度", 6), _size("element_height", "单元高度", 6),
                angle("rotation", "整体旋转"), _coord("offset_x", "原点 X"), _coord("offset_y", "原点 Y"),
            ]},
            "radial": {"label": "放射布局", "parameters": [
                _p("count", "数量", "integer", 12, min=1, max=3000, step=1),
                _coord("center_x", "中心 X"), _coord("center_y", "中心 Y"),
                angle("start_angle", "起始角度"), angle("end_angle", "结束角度", 360),
                _p("base_radius", "起始半径", "number", 50, min=0, max=10000, step=0.1, unit="mm"),
                _p("end_radius", "结束半径", "number", 50, min=0, max=10000, step=0.1, unit="mm"),
                _size("element_width", "单元宽度", 6), _size("element_height", "单元高度", 6),
                angle("rotation", "整体旋转"),
            ]},
            "along_curve": {"label": "沿曲线布局", "parameters": [
                _p("count", "数量", "integer", 2, min=1, max=3000, step=1),
                _size("element_width", "单元宽度", 6), _size("element_height", "单元高度", 6),
                _p("rotate_along_path", "沿路径旋转", "boolean", True),
            ]},
        },
        "field": {
            "linear": {"label": "线性场", "parameters": [angle("angle", "方向角度"),
                _coord("start", "起点"), _coord("end", "终点", 100)]},
            "wave": {"label": "波浪场", "parameters": [angle("angle", "角度"),
                _size("wavelength", "波长", 50), _p("phase", "相位", "number", 0, min=-100, max=100, step=0.1),
                _p("amplitude", "振幅", "number", 1, min=0, max=1, step=0.01),
                _p("offset", "基线", "number", 0, min=0, max=1, step=0.01), invert]},
            "ring": {"label": "环形／径向场", "parameters": [
                _coord("center_x", "中心 X"), _coord("center_y", "中心 Y"),
                _p("radius", "半径", "number", 50, min=0, max=10000, step=0.1, unit="mm"),
                _size("ring_width", "环宽", 10),
                _p("falloff", "衰减", "number", 1, min=0.01, max=20, step=0.1), invert]},
        },
        "modifier": {
            "size": {"label": "尺寸", "parameters": [
                _p("min_output", "最小输出", "number", 0, min=0, max=10000, step=0.1),
                _p("max_output", "最大输出", "number", 1, min=0, max=10000, step=0.1),
                _p("strength", "作用强度", "number", 1, min=0, max=1, step=0.01),
                _p("falloff", "衰减", "number", 1, min=0.01, max=20, step=0.1)]},
            "rotation": {"label": "旋转", "parameters": [
                _p("min_output", "最小输出", "number", 0, min=-10000, max=10000, step=0.1, unit="°"),
                _p("max_output", "最大输出", "number", 1, min=-10000, max=10000, step=0.1, unit="°"),
                _p("strength", "作用强度", "number", 1, min=0, max=1, step=0.01),
                _p("falloff", "衰减", "number", 1, min=0.01, max=20, step=0.1)]},
        },
    }}


def validate_parameter(definition: dict[str, Any], value: Any) -> Any:
    """Reject invalid primitives before they enter a document edit."""
    kind = definition["type"]
    if kind == "boolean":
        if type(value) is not bool:
            raise ValueError("布尔参数无效。")
        return value
    if kind == "select":
        if value not in [option["value"] for option in definition["options"]]:
            raise ValueError("选项不在允许范围内。")
        return value
    if kind not in ("number", "integer") or type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("参数必须是有限数字。")
    if kind == "integer" and not float(value).is_integer():
        raise ValueError("参数必须是整数。")
    if definition["min"] is not None and value < definition["min"]:
        raise ValueError("参数小于允许的最小值。")
    if definition["max"] is not None and value > definition["max"]:
        raise ValueError("参数大于允许的最大值。")
    return value
