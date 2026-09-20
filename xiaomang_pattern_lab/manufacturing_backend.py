"""Backend boundary for the first derived Manufacturing2DGeometry → Mesh step.

No design Element, canvas, modifier, project state, STL writer, or UI enters
this module.  The current implementation is deliberately small: valid mm
polygons are triangulated and extruded from Z=0 to ``height_mm``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Any

from .manufacturing_geometry import Bounds, Manufacturing2DGeometry


@dataclass(frozen=True)
class ManufacturingMeshResult:
    """Derived mesh result; this is not a document and is never persisted by V."""

    mesh: Any
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    vertex_count: int
    face_count: int
    component_count: int
    height_mm: float
    backend_name: str
    is_watertight: bool
    warnings: tuple[str, ...] = ()

    @property
    def size(self) -> tuple[float, float, float]:
        lower, upper = self.bounds
        return upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2]


class ManufacturingBackend(ABC):
    """The sole 3D boundary: derived 2D manufacturing geometry in, Mesh out."""

    @abstractmethod
    def extrude(self, geometry: Manufacturing2DGeometry, height_mm: float = 2.0) -> ManufacturingMeshResult:
        raise NotImplementedError


class TrimeshBackend(ManufacturingBackend):
    """A local, deterministic Polygon-with-Holes extrusion backend.

    Imports are deliberately local so importing the desktop package itself
    does not make an optional future manufacturing dependency a UI concern.
    """

    backend_name = "trimesh-earcut"

    def extrude(self, geometry: Manufacturing2DGeometry, height_mm: float = 2.0) -> ManufacturingMeshResult:
        height = _valid_height(height_mm)
        if geometry.units != "mm":
            raise ValueError("ManufacturingBackend 只接受单位为 mm 的 Manufacturing2DGeometry。")
        if not geometry.polygons:
            raise ValueError("没有可挤出的制造面积几何。")
        try:
            import numpy as np
            import trimesh
            from shapely.geometry import Polygon
        except ImportError as error:
            raise RuntimeError("缺少 Gate V 制造依赖：请安装 trimesh、shapely、mapbox-earcut。") from error

        meshes = []
        for polygon in geometry.polygons:
            shape = Polygon(polygon.outer, polygon.holes)
            if shape.is_empty or not shape.is_valid or shape.area <= 0:
                raise ValueError("制造 Polygon 无效或面积为零：%s" % polygon.source_element_id)
            # mapbox-earcut is an explicit requirement.  It avoids guessing a
            # hand-written hole triangulation and works with Windows wheels.
            mesh = trimesh.creation.extrude_polygon(shape, height=height, engine="earcut")
            if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
                raise ValueError("未生成有效 Mesh：%s" % polygon.source_element_id)
            meshes.append(mesh)
        mesh = trimesh.util.concatenate(meshes)
        if not bool(np.isfinite(mesh.vertices).all()):
            raise ValueError("生成的 Mesh 含有 NaN 或 Infinity 坐标。")
        lower, upper = mesh.bounds
        bounds = (
            (float(lower[0]), float(lower[1]), float(lower[2])),
            (float(upper[0]), float(upper[1]), float(upper[2])),
        )
        return ManufacturingMeshResult(
            mesh=mesh,
            bounds=bounds,
            vertex_count=int(len(mesh.vertices)),
            face_count=int(len(mesh.faces)),
            # No Boolean union in Gate V: every ManufacturingPolygon remains
            # its own body even when two boundaries touch.
            component_count=len(meshes),
            height_mm=height,
            backend_name=self.backend_name,
            is_watertight=bool(mesh.is_watertight),
        )


@dataclass(frozen=True)
class ManufacturingBuildResult:
    """Session-level join of U.5 conversion evidence and the derived Mesh."""

    conversion: Any
    mesh_result: ManufacturingMeshResult


def _valid_height(value: float) -> float:
    try:
        height = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("height_mm 必须是有限正数。") from error
    if not math.isfinite(height) or height <= 0:
        raise ValueError("height_mm 必须是有限正数。")
    return height
