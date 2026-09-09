"""EditablePatternDocument 到最终制造工作单的确定性转换。"""
from __future__ import annotations

import math

from .editable_document import EditablePatternDocument


def document_to_primitives(document: EditablePatternDocument) -> list[dict]:
    """只读取当前物化 elements，绝不回读 Raster 或旧 Generator。"""
    primitives: list[dict] = []
    for element in document.elements:
        if not element.enabled or element.opacity <= 0.0:
            continue
        kind = str(element.primitive_type).lower()
        radius_x = max(0.001, float(element.width) * 0.5)
        radius_y = max(0.001, float(element.height) * 0.5)
        common = {
            "element_id": element.id,
            "x": float(element.x), "y": float(element.y),
            "rotation": float(element.rotation),
            "source": "editable_pattern_document",
        }
        if kind == "line":
            half_length = max(0.001, float(element.width) * 0.5)
            angle = math.radians(float(element.rotation))
            dx, dy = math.cos(angle) * half_length, math.sin(angle) * half_length
            primitives.append({**common, "kind": "line", "x": element.x - dx, "y": element.y - dy,
                               "x2": element.x + dx, "y2": element.y + dy,
                               "size": max(0.001, float(element.height))})
        elif kind in {"triangle", "square"}:
            primitives.append({**common, "kind": kind, "size": max(radius_x, radius_y)})
        elif abs(radius_x - radius_y) > 1e-6 or kind == "ellipse":
            primitives.append({**common, "kind": "ellipse", "size": max(radius_x, radius_y),
                               "radius_x": radius_x, "radius_y": radius_y})
        else:
            primitives.append({**common, "kind": "dot", "size": max(0.001, float(element.radius))})
    return primitives
