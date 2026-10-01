"""F1: optional, headless fabric base derived from evaluated manufacturing bounds.

The configuration lives in PatternDocument.metadata; meshes never do.  A
single 2D union is used for the grid so intersecting strips form one body.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .manufacturing_backend import ManufacturingMeshResult, TrimeshBackend
from .manufacturing_geometry import Manufacturing2DGeometry, ManufacturingPolygon


FABRIC_CONFIG_KEY = "fabric_config"


def _positive(value: Any, name: str, *, allow_zero: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("%s 必须是有限毫米数值。" % name)
    invalid = value < 0 if allow_zero else value <= 0
    if invalid:
        raise ValueError("%s %s。" % (name, "不能小于 0" if allow_zero else "必须大于 0"))
    return float(value)


@dataclass(frozen=True)
class BaseDefinition:
    type: str
    thickness_mm: float
    margin_mm: float
    spacing_x_mm: float | None = None
    spacing_y_mm: float | None = None
    line_width_mm: float | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BaseDefinition":
        kind = raw.get("type")
        if kind not in ("solid", "grid"):
            raise ValueError("Fabric Base 目前只支持 solid 或 grid。")
        thickness = _positive(raw.get("thickness_mm"), "基底厚度")
        margin = _positive(raw.get("margin_mm", 0), "边距", allow_zero=True)
        if kind == "solid":
            return cls(kind, thickness, margin)
        sx = _positive(raw.get("spacing_x_mm"), "水平间距")
        sy = _positive(raw.get("spacing_y_mm"), "垂直间距")
        width = _positive(raw.get("line_width_mm"), "网格线宽")
        if width > min(sx, sy):
            raise ValueError("网格线宽不能大于水平或垂直间距。")
        return cls(kind, thickness, margin, sx, sy, width)


@dataclass(frozen=True)
class FabricConfig:
    config_version: int
    base: BaseDefinition

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FabricConfig":
        if type(raw.get("config_version")) is not int or raw["config_version"] != 1:
            raise ValueError("不支持的 Fabric 配置版本。")
        base = raw.get("base")
        if not isinstance(base, Mapping):
            raise ValueError("Fabric 配置缺少基底参数。")
        return cls(1, BaseDefinition.from_mapping(base))


def fabric_config_from_document(document) -> FabricConfig | None:
    raw = document.metadata.get(FABRIC_CONFIG_KEY)
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("Fabric 配置必须是对象。")
    return FabricConfig.from_mapping(raw)


class FabricBaseBuilder:
    """Create a solid/grid base in mm, independent of any UI or unit cell."""

    def build(self, bounds_mm: tuple[float, float, float, float], base: BaseDefinition) -> ManufacturingMeshResult:
        if len(bounds_mm) != 4 or any(not math.isfinite(value) for value in bounds_mm):
            raise ValueError("二维制造边界必须是有限毫米坐标。")
        min_x, min_y, max_x, max_y = bounds_mm
        if max_x <= min_x or max_y <= min_y:
            raise ValueError("二维制造边界必须有正面积。")
        left, bottom = min_x - base.margin_mm, min_y - base.margin_mm
        right, top = max_x + base.margin_mm, max_y + base.margin_mm
        if base.type == "solid":
            polygons = (ManufacturingPolygon("fabric-base", (
                (left, bottom), (right, bottom), (right, top), (left, top))),)
        else:
            polygons = self._grid_polygons(left, bottom, right, top, base)
        geometry = Manufacturing2DGeometry(polygons, "mm", (left, bottom, right, top))
        return TrimeshBackend().extrude(geometry, base.thickness_mm)

    @staticmethod
    def _grid_polygons(left: float, bottom: float, right: float, top: float,
                       base: BaseDefinition) -> tuple[ManufacturingPolygon, ...]:
        from shapely.geometry import box
        from shapely.ops import unary_union

        sx, sy, width = base.spacing_x_mm, base.spacing_y_mm, base.line_width_mm
        assert sx is not None and sy is not None and width is not None
        nx = math.ceil((right - left) / sx)
        ny = math.ceil((top - bottom) / sy)
        if (nx + 1) + (ny + 1) > 10000:
            raise ValueError("网格线数量超过 F1 安全上限，请增大间距。")
        half = width / 2
        strips = [box(max(left, x - half), bottom, min(right, x + half), top)
                  for x in [left + i * sx for i in range(nx)] + [right]]
        strips.extend(box(left, max(bottom, y - half), right, min(top, y + half))
                      for y in [bottom + i * sy for i in range(ny)] + [top])
        union = unary_union(strips)
        if union.geom_type != "Polygon" or union.is_empty or not union.is_valid:
            raise ValueError("网格基底未形成单个有效连通区域。")
        # The union can retain collinear exterior vertices at clipped strip
        # ends. Earcut may create duplicate side faces on those zero-turn
        # vertices. Remove only sub-nanometre collinearity, preserving topology.
        simplified = union.simplify(1e-9, preserve_topology=True)
        if not union.equals(simplified):
            raise ValueError("网格轮廓简化改变了制造面积。")
        union = simplified
        return (ManufacturingPolygon("fabric-base",
                tuple((float(x), float(y)) for x, y in union.exterior.coords[:-1]),
                tuple(tuple((float(x), float(y)) for x, y in ring.coords[:-1])
                      for ring in union.interiors)),)
