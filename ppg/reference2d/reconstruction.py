from __future__ import annotations

from .models import DotFeature, EditableGeometry
from .editable_document import EditableElement, EditablePatternDocument


def build_editable_geometry(features: list[DotFeature]) -> EditableGeometry:
    dots = []; lines = []; shapes = []
    for feature in features:
        if feature.element_type == "line":
            length = max(feature.radius_x, feature.radius_y) * 1.8
            import math
            angle = math.radians(feature.rotation)
            dx, dy = math.cos(angle) * length, math.sin(angle) * length
            lines.append({"id": feature.id, "control_points": [[feature.center_x - dx, feature.center_y - dy], [feature.center_x + dx, feature.center_y + dy]], "width": feature.diameter, "rotation": feature.rotation, "closed": False, "region_id": feature.region_id, "source_confidence": feature.confidence})
        elif feature.element_type == "shape":
            shapes.append({"id": feature.id, "center": [feature.center_x, feature.center_y], "radius_x": feature.radius_x, "radius_y": feature.radius_y, "rotation": feature.rotation, "fill": "black", "region_id": feature.region_id, "source_confidence": feature.confidence})
        else:
            dots.append({"id": feature.id, "position": [feature.center_x, feature.center_y], "radius_x": feature.radius_x, "radius_y": feature.radius_y, "rotation": feature.rotation, "opacity": 1.0, "fill": "black", "stroke": None, "region_id": feature.region_id, "source_confidence": feature.confidence, "locked": False})
    return EditableGeometry(tuple(dots), tuple(lines), tuple(shapes), {"type": "binary", "feather": 0.0, "source": "detected_components"})


def build_editable_document(features: list[DotFeature], *, width_px: int, height_px: int, source_path: str,
                            generator: dict | None = None, modifiers: tuple[dict, ...] = (), fields: dict | None = None,
                            reference: dict | None = None, metadata: dict | None = None) -> EditablePatternDocument:
    """把所有检测结果变成真正可编辑的 Element，不依赖 Generator 拟合成功。"""
    elements: list[EditableElement] = []
    for index, feature in enumerate(features, 1):
        elements.append(EditableElement(
            id=f"element-{index:04d}", primitive_type={"dot": "circle" if abs(feature.radius_x-feature.radius_y) < .5 else "ellipse", "line": "line", "shape": "shape"}.get(feature.element_type, "dot"),
            x=float(feature.center_x), y=float(feature.center_y), width=max(.1, feature.radius_x * 2.0), height=max(.1, feature.radius_y * 2.0), radius=max(.1, (feature.radius_x + feature.radius_y) / 2.0),
            rotation=float(feature.rotation), opacity=1.0, enabled=True, group_id=None, source="primitive_detection", confidence=float(feature.confidence),
        ))
    selected_generator = dict(generator or {"mode": "direct", "base": None, "score": 0.0})
    if selected_generator.get("mode") not in ("direct", "parametric"): selected_generator["mode"] = "direct"
    document = EditablePatternDocument(
        canvas={"width": 100.0, "height": 100.0, "units": "percent", "source_width_px": int(width_px), "source_height_px": int(height_px)},
        reference={"source_path": str(source_path), "width_px": int(width_px), "height_px": int(height_px), "visible": True, **(reference or {})},
        generator=selected_generator, modifiers=[dict(item) for item in modifiers], elements=elements,
        base_elements=[item.clone() for item in elements],
        masks=[{"type": "binary", "source": "preprocessed_mask"}], fields=dict(fields or {}),
        metadata={"stage": "A: Geometry Reconstruction", "element_count": len(elements), **dict(metadata or {})},
    )
    # 初始 Rebuild 应与检测的 Geometry 一致；它只是建立可重复的基线，
    # 不再读取原始 Raster。
    document.rebuild()
    return document
