"""最终制造模型使用的二维工作单工具。

这里不包含 Viewer、临时 Mesh 或相机状态。它只负责把二维图元规范到 mm
工作坐标，并将可保存的高度控制应用到最终制造工作单。
"""
from __future__ import annotations

import math


def primitives_bounds(primitives: list[dict]) -> tuple[float, float, float, float]:
    """返回二维制造工作单边界，保留椭圆的独立横纵半径。"""
    points: list[tuple[float, float]] = []
    for item in primitives:
        try:
            size = max(0.0, float(item.get("size", 0.0)))
            radius_x = max(0.0, float(item.get("radius_x", size)))
            radius_y = max(0.0, float(item.get("radius_y", size)))
            x, y = float(item["x"]), float(item["y"])
            if item.get("kind") == "ellipse":
                angle = math.radians(float(item.get("rotation", 0.0)))
                extent_x = math.hypot(radius_x * math.cos(angle), radius_y * math.sin(angle))
                extent_y = math.hypot(radius_x * math.sin(angle), radius_y * math.cos(angle))
            else:
                extent_x, extent_y = radius_x, radius_y
            points.extend(((x - extent_x, y - extent_y), (x + extent_x, y + extent_y)))
            if item.get("kind") == "line" and item.get("x2") is not None and item.get("y2") is not None:
                x2, y2 = float(item["x2"]), float(item["y2"])
                points.extend(((x2 - radius_x, y2 - radius_y), (x2 + radius_x, y2 + radius_y)))
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        return 0.0, 0.0, 0.0, 0.0
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def scale_primitives_to_width(primitives: list[dict], target_width_mm: float) -> list[dict]:
    """将二维设计等比缩放至最终制造宽度；内部唯一单位为 mm。"""
    min_x, min_y, max_x, _max_y = primitives_bounds(primitives)
    width = max(0.0001, max_x - min_x)
    factor = max(0.001, float(target_width_mm)) / width
    output: list[dict] = []
    for source in primitives:
        item = dict(source)
        for key in ("x", "y", "x2", "y2"):
            if item.get(key) is not None:
                origin = min_x if key.startswith("x") else min_y
                item[key] = (float(item[key]) - origin) * factor
        for key in ("size", "radius_x", "radius_y"):
            if item.get(key) is not None:
                item[key] = float(item[key]) * factor
        output.append(item)
    return output


def _height_at(x: float, y: float, base_height: float, controls: list[dict]) -> float:
    height = base_height
    for point in controls:
        try:
            radius = max(0.1, float(point.get("radius", 12.0)))
            distance = math.hypot(x - float(point["x"]), y - float(point["y"]))
            if distance >= radius:
                continue
            falloff = max(0.1, float(point.get("falloff", 55.0))) / 100.0
            influence = (1.0 - distance / radius) ** (1.0 + (1.0 - falloff) * 3.0)
            height += float(point.get("delta", 0.0)) * influence
        except (KeyError, TypeError, ValueError):
            continue
    return max(0.1, height)


def apply_height_field(primitives: list[dict], base_height: float, controls: list[dict]) -> list[dict]:
    """将高度场写入最终制造工作单，不创建任何预览网格。"""
    result: list[dict] = []
    for source in primitives:
        item = dict(source)
        x, y = float(item["x"]), float(item["y"])
        if item.get("kind") == "line" and item.get("x2") is not None and item.get("y2") is not None:
            x = (x + float(item["x2"])) * 0.5
            y = (y + float(item["y2"])) * 0.5
        item["height"] = round(_height_at(x, y, base_height, controls), 5)
        result.append(item)
    return result
