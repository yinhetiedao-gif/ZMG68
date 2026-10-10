"""F2 unit-cell prototype meshes. Geometry is derived once per definition.

All prototypes use world millimetres, are centred on XY, and start at Z=0.
They are preview geometry, not part of the validated F1 manufacturing STL.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping


CELL_TYPES = ("cylinder", "cone", "pyramid", "double_tower", "fin",
              "dome", "frustum", "hex_prism", "wedge", "cross", "ring")


def _dimension(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} 必须是大于 0 的有限毫米数值。")
    return float(value)


@dataclass(frozen=True)
class UnitCellDefinition:
    type: str
    width_mm: float
    depth_mm: float
    height_mm: float
    shape_ratio: float = 0.5

    def __post_init__(self) -> None:
        if self.type not in CELL_TYPES:
            raise ValueError("不支持的 Fabric Unit Cell 类型。")
        for value, name in ((self.width_mm, "单元宽度"), (self.depth_mm, "单元深度"),
                            (self.height_mm, "单元高度")):
            _dimension(value, name)
        if self.type in ("frustum", "cross", "ring"):
            if type(self.shape_ratio) not in (int, float) or not math.isfinite(self.shape_ratio) or not .1 <= self.shape_ratio <= .9:
                raise ValueError("造型比例必须在 0.1–0.9 之间。")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "UnitCellDefinition":
        kind = raw.get("type")
        if kind not in CELL_TYPES:
            raise ValueError("不支持的 Fabric Unit Cell 类型。")
        return cls(kind, _dimension(raw.get("width_mm"), "单元宽度"),
                   _dimension(raw.get("depth_mm"), "单元深度"),
                   _dimension(raw.get("height_mm"), "单元高度"), raw.get("shape_ratio", .5))


class UnitCellRegistry:
    """Small explicit registry: new cells do not add branches to FabricBuilder."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[UnitCellDefinition], Any]] = {}

    def register(self, kind: str, factory: Callable[[UnitCellDefinition], Any]) -> None:
        if kind in self._factories:
            raise ValueError(f"Unit Cell 已注册：{kind}")
        self._factories[kind] = factory

    def create(self, definition: UnitCellDefinition):
        try:
            mesh = self._factories[definition.type](definition)
        except KeyError as error:
            raise ValueError(f"未注册 Unit Cell：{definition.type}") from error
        import numpy as np
        if not bool(np.isfinite(mesh.vertices).all()) or mesh.is_empty:
            raise ValueError("Unit Cell 几何无效。")
        lower, upper = mesh.bounds
        expected = (definition.width_mm, definition.depth_mm, definition.height_mm)
        if any(abs(float(upper[i] - lower[i]) - expected[i]) > 1e-6 for i in range(3)):
            raise ValueError("Unit Cell 原型尺寸与定义不一致。")
        if abs(float(lower[2])) > 1e-8:
            raise ValueError("Unit Cell 底部必须位于局部 Z=0。")
        return mesh


def _round_cell(definition: UnitCellDefinition, kind: str):
    import trimesh
    create = trimesh.creation.cylinder if kind == "cylinder" else trimesh.creation.cone
    mesh = create(radius=0.5, height=1, sections=24)
    vertices = mesh.vertices.copy()
    vertices[:, 2] -= vertices[:, 2].min()
    vertices *= (definition.width_mm, definition.depth_mm, definition.height_mm)
    mesh.vertices = vertices
    return mesh


def _pyramid(definition: UnitCellDefinition):
    import trimesh
    x, y, h = definition.width_mm / 2, definition.depth_mm / 2, definition.height_mm
    vertices = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (0, 0, h)]
    faces = [(0, 2, 1), (0, 3, 2), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _double_tower(definition: UnitCellDefinition):
    import trimesh
    left = _round_cell(UnitCellDefinition("cylinder", definition.width_mm / 2,
                                          definition.depth_mm, definition.height_mm), "cylinder")
    right = left.copy()
    left.apply_translation((-definition.width_mm / 4, 0, 0))
    right.apply_translation((definition.width_mm / 4, 0, 0))
    return trimesh.util.concatenate((left, right))


def _fin(definition: UnitCellDefinition, wedge: bool = False):
    import trimesh
    x, y, h = definition.width_mm / 2, definition.depth_mm / 2, definition.height_mm
    peak = x if wedge else 0
    vertices = [(-x, -y, 0), (x, -y, 0), (peak, -y, h),
                (-x, y, 0), (x, y, 0), (peak, y, h)]
    # Explicit outward construction winding (the former list enclosed a
    # negative volume). No runtime mesh repair/inversion or vertex change.
    faces = [(0, 1, 2), (3, 5, 4), (0, 4, 1), (0, 3, 4),
             (1, 5, 2), (1, 4, 5), (2, 3, 0), (2, 5, 3)]
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _round_profile(definition: UnitCellDefinition, dome: bool = False):
    """Closed indexed surface, with a single dome pole (no collapsed pole quads)."""
    import trimesh
    count = 24
    profile = [(0.5 * math.cos(j * math.pi / 16), math.sin(j * math.pi / 16))
               for j in range(8)] if dome else [(0.5, 0), (0.5 * definition.shape_ratio, 1)]
    vertices = [(r * math.cos(i * math.tau / count), r * math.sin(i * math.tau / count), z)
                for r, z in profile for i in range(count)]
    faces = []
    for j in range(len(profile) - 1):
        for i in range(count):
            a, b = j * count + i, j * count + (i + 1) % count
            faces.extend([(a, b, b + count), (a, b + count, a + count)])
    bottom = len(vertices)
    vertices.append((0, 0, 0))
    top = len(vertices)
    vertices.append((0, 0, 1))
    last = (len(profile) - 1) * count
    for i in range(count):
        n = (i + 1) % count
        faces.extend([(bottom, n, i), (last + i, last + n, top)])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.apply_scale((definition.width_mm, definition.depth_mm, definition.height_mm))
    return mesh


def _polygon_cell(definition: UnitCellDefinition):
    import trimesh
    from shapely.geometry import Polygon
    if definition.type == "hex_prism":
        polygon = Polygon([(.5,0),(.25,.5),(-.25,.5),(-.5,0),(-.25,-.5),(.25,-.5)])
    elif definition.type == "cross":
        a = definition.shape_ratio / 2
        polygon = Polygon([(-a,-.5),(a,-.5),(a,-a),(.5,-a),(.5,a),(a,a),
                           (a,.5),(-a,.5),(-a,a),(-.5,a),(-.5,-a),(-a,-a)])
    mesh = trimesh.creation.extrude_polygon(polygon, height=1, engine="earcut")
    mesh.apply_scale((definition.width_mm, definition.depth_mm, definition.height_mm))
    return mesh


def _ring(definition: UnitCellDefinition):
    """Indexed annular prism: inner wall and both annular caps, no triangulator bridge."""
    import trimesh
    n = 24
    vertices = [(r * math.cos(i * math.tau / n), r * math.sin(i * math.tau / n), z)
                for z, r in [(0,.5),(0,.5*definition.shape_ratio),(1,.5),(1,.5*definition.shape_ratio)] for i in range(n)]
    faces = []
    for i in range(n):
        j = (i+1) % n
        # Outer, inner, lower and upper surfaces; explicit outward winding.
        for a,b,c,d in [(i,j,2*n+j,2*n+i),(n+j,n+i,3*n+i,3*n+j),
                        (j,i,n+i,n+j),(2*n+i,2*n+j,3*n+j,3*n+i)]:
            faces.extend([(a,b,c),(a,c,d)])
    mesh = trimesh.Trimesh(vertices=vertices,faces=faces,process=False)
    mesh.apply_scale((definition.width_mm,definition.depth_mm,definition.height_mm))
    return mesh


UNIT_CELL_REGISTRY = UnitCellRegistry()
UNIT_CELL_REGISTRY.register("cylinder", lambda definition: _round_cell(definition, "cylinder"))
UNIT_CELL_REGISTRY.register("cone", lambda definition: _round_cell(definition, "cone"))
UNIT_CELL_REGISTRY.register("pyramid", _pyramid)
UNIT_CELL_REGISTRY.register("double_tower", _double_tower)
UNIT_CELL_REGISTRY.register("fin", _fin)
UNIT_CELL_REGISTRY.register("dome", lambda definition: _round_profile(definition, True))
UNIT_CELL_REGISTRY.register("frustum", _round_profile)
UNIT_CELL_REGISTRY.register("hex_prism", _polygon_cell)
UNIT_CELL_REGISTRY.register("wedge", lambda definition: _fin(definition, True))
UNIT_CELL_REGISTRY.register("cross", _polygon_cell)
UNIT_CELL_REGISTRY.register("ring", _ring)
