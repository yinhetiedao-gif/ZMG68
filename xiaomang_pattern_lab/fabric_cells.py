"""F2 unit-cell prototype meshes. Geometry is derived once per definition.

All prototypes use world millimetres, are centred on XY, and start at Z=0.
They are preview geometry, not part of the validated F1 manufacturing STL.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping


CELL_TYPES = ("cylinder", "cone", "pyramid", "double_tower", "fin")


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

    def __post_init__(self) -> None:
        if self.type not in CELL_TYPES:
            raise ValueError("不支持的 Fabric Unit Cell 类型。")
        for value, name in ((self.width_mm, "单元宽度"), (self.depth_mm, "单元深度"),
                            (self.height_mm, "单元高度")):
            _dimension(value, name)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "UnitCellDefinition":
        kind = raw.get("type")
        if kind not in CELL_TYPES:
            raise ValueError("不支持的 Fabric Unit Cell 类型。")
        return cls(kind, _dimension(raw.get("width_mm"), "单元宽度"),
                   _dimension(raw.get("depth_mm"), "单元深度"),
                   _dimension(raw.get("height_mm"), "单元高度"))


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


def _fin(definition: UnitCellDefinition):
    import trimesh
    x, y, h = definition.width_mm / 2, definition.depth_mm / 2, definition.height_mm
    vertices = [(-x, -y, 0), (x, -y, 0), (0, -y, h),
                (-x, y, 0), (x, y, 0), (0, y, h)]
    # Explicit outward construction winding (the former list enclosed a
    # negative volume). No runtime mesh repair/inversion or vertex change.
    faces = [(0, 1, 2), (3, 5, 4), (0, 4, 1), (0, 3, 4),
             (1, 5, 2), (1, 4, 5), (2, 3, 0), (2, 5, 3)]
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


UNIT_CELL_REGISTRY = UnitCellRegistry()
UNIT_CELL_REGISTRY.register("cylinder", lambda definition: _round_cell(definition, "cylinder"))
UNIT_CELL_REGISTRY.register("cone", lambda definition: _round_cell(definition, "cone"))
UNIT_CELL_REGISTRY.register("pyramid", _pyramid)
UNIT_CELL_REGISTRY.register("double_tower", _double_tower)
UNIT_CELL_REGISTRY.register("fin", _fin)
