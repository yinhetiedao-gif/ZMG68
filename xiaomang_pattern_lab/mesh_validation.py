"""Gate W-Core: read-only manufacturing Mesh validation.

This module intentionally accepts only the derived ``ManufacturingMeshResult``
produced by Gate V.  It never reaches back into a PatternDocument, evaluates
2D geometry, or calls a trimesh repair/process operation.  The topology report
is calculated directly from immutable views of the mesh's vertices and faces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Any

from .manufacturing_backend import ManufacturingMeshResult


@dataclass(frozen=True)
class MeshValidationIssue:
    """One read-only manufacturing Mesh observation."""

    issue_type: str
    severity: str
    message: str
    component_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeshValidationReport:
    """Small, stable Gate W report; multiple bodies are a warning, not failure."""

    vertex_count: int
    face_count: int
    finite_coordinates: bool
    is_watertight: bool
    boundary_edge_count: int
    non_manifold_edge_count: int
    degenerate_face_count: int
    component_count: int
    warning_count: int
    error_count: int
    issues: tuple[MeshValidationIssue, ...] = ()
    # Performance telemetry is intentionally excluded from structural report
    # equality: the same read-only Mesh must yield the same validation facts.
    duration_ms: float = field(default=0.0, compare=False)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


class MeshValidator:
    """Analyze a Gate V Mesh without normalizing, repairing, or mutating it.

    ``degenerate_face_epsilon_mm2`` is an area tolerance in squared millimetres.
    It is deliberately explicit, so this core check does not pretend to be a
    printer wall-thickness or feature-size policy.
    """

    def __init__(self, *, degenerate_face_epsilon_mm2: float = 1e-12) -> None:
        epsilon = float(degenerate_face_epsilon_mm2)
        if not math.isfinite(epsilon) or epsilon < 0:
            raise ValueError("degenerate_face_epsilon_mm2 必须是有限的非负数。")
        self.degenerate_face_epsilon_mm2 = epsilon

    def validate(self, result: ManufacturingMeshResult) -> MeshValidationReport:
        """Return a deterministic report while leaving ``result.mesh`` untouched."""

        started = time.perf_counter()
        import numpy as np

        issues: list[MeshValidationIssue] = []
        vertices, faces, shape_ok = _mesh_arrays(result.mesh, np)
        vertex_count = int(len(vertices))
        face_count = int(len(faces))
        finite = bool(shape_ok and np.isfinite(vertices).all())
        if not shape_ok:
            issues.append(MeshValidationIssue(
                "malformed_mesh", "error", "Mesh 顶点或三角面数组格式无效。",
            ))
        if not finite:
            issues.append(MeshValidationIssue(
                "non_finite_coordinates", "error", "Mesh 包含 NaN、Infinity 或非法顶点数组。",
            ))

        valid_faces = _valid_face_rows(faces, vertex_count, np)
        malformed_faces = face_count - int(len(valid_faces))
        if malformed_faces:
            issues.append(MeshValidationIssue(
                "invalid_face_indices", "error", "Mesh 含有越界或格式错误的三角面。",
                metadata={"invalid_face_count": malformed_faces},
            ))

        edge_faces = _edge_face_map(valid_faces)
        boundary_edges = sum(1 for linked in edge_faces.values() if len(linked) == 1)
        non_manifold_edges = sum(1 for linked in edge_faces.values() if len(linked) > 2)
        degenerate_faces = _degenerate_face_count(vertices, valid_faces, finite, self.degenerate_face_epsilon_mm2, np)
        component_count = _face_component_count(len(valid_faces), edge_faces)

        # This is a direct topological closure check.  It intentionally does
        # not ask trimesh to process or repair the mesh, and separate closed
        # bodies still correctly report watertight=True.
        watertight = bool(
            finite and not malformed_faces and len(valid_faces) > 0
            and boundary_edges == 0 and non_manifold_edges == 0
        )
        if not watertight:
            issues.append(MeshValidationIssue(
                "non_watertight", "error", "Mesh 存在边界边、非流形边或无效拓扑，未形成封闭实体。",
                metadata={"boundary_edge_count": boundary_edges, "non_manifold_edge_count": non_manifold_edges},
            ))
        if non_manifold_edges:
            issues.append(MeshValidationIssue(
                "non_manifold_edges", "error", "Mesh 存在被超过两个面共享的边。",
                metadata={"non_manifold_edge_count": non_manifold_edges},
            ))
        if degenerate_faces:
            issues.append(MeshValidationIssue(
                "degenerate_faces", "error", "Mesh 存在面积接近零或顶点折叠的三角面。",
                metadata={
                    "degenerate_face_count": degenerate_faces,
                    "epsilon_mm2": self.degenerate_face_epsilon_mm2,
                },
            ))
        if component_count > 1:
            issues.append(MeshValidationIssue(
                "multiple_components", "warning", "Mesh 包含多个独立拓扑组件；这是事实，不在 Gate W 自动修复。",
                metadata={"component_count": component_count},
            ))

        errors = sum(issue.severity == "error" for issue in issues)
        warnings = sum(issue.severity == "warning" for issue in issues)
        return MeshValidationReport(
            vertex_count=vertex_count,
            face_count=face_count,
            finite_coordinates=finite,
            is_watertight=watertight,
            boundary_edge_count=boundary_edges,
            non_manifold_edge_count=non_manifold_edges,
            degenerate_face_count=degenerate_faces,
            component_count=component_count,
            warning_count=warnings,
            error_count=errors,
            issues=tuple(issues),
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )


def _mesh_arrays(mesh: Any, np: Any) -> tuple[Any, Any, bool]:
    """Read arrays only; failed coercion becomes an explicit report issue."""

    try:
        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces)
    except (AttributeError, TypeError, ValueError):
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=int), False
    valid_shape = vertices.ndim == 2 and vertices.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 3
    if not valid_shape:
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=int), False
    return vertices, faces, True


def _valid_face_rows(faces: Any, vertex_count: int, np: Any) -> list[tuple[int, int, int]]:
    valid: list[tuple[int, int, int]] = []
    for face in faces:
        try:
            numeric = np.asarray(face, dtype=float)
        except (TypeError, ValueError):
            continue
        if not bool(np.isfinite(numeric).all()) or not bool(np.equal(numeric, np.floor(numeric)).all()):
            continue
        indexes = tuple(int(value) for value in numeric)
        if all(0 <= value < vertex_count for value in indexes):
            valid.append(indexes)
    return valid


def _edge_face_map(faces: list[tuple[int, int, int]]) -> dict[tuple[int, int], list[int]]:
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, (first, second, third) in enumerate(faces):
        for left, right in ((first, second), (second, third), (third, first)):
            edge_faces.setdefault((min(left, right), max(left, right)), []).append(face_index)
    return edge_faces


def _degenerate_face_count(vertices: Any, faces: list[tuple[int, int, int]], finite: bool, epsilon: float, np: Any) -> int:
    if not finite:
        return 0
    count = 0
    for first, second, third in faces:
        a, b, c = vertices[first], vertices[second], vertices[third]
        # Cross-product magnitude / 2 is the triangle area in mm².  Duplicate
        # vertex indexes naturally produce area zero and are therefore caught.
        area = float(np.linalg.norm(np.cross(b - a, c - a)) * 0.5)
        if not math.isfinite(area) or area <= epsilon:
            count += 1
    return count


def _face_component_count(face_count: int, edge_faces: dict[tuple[int, int], list[int]]) -> int:
    if face_count == 0:
        return 0
    parent = list(range(face_count))
    for linked_faces in edge_faces.values():
        root = linked_faces[0]
        for child in linked_faces[1:]:
            _union(parent, root, child)
    return len({_find(parent, index) for index in range(face_count)})


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union(parent: list[int], first: int, second: int) -> None:
    root_first, root_second = _find(parent, first), _find(parent, second)
    if root_first != root_second:
        parent[root_second] = root_first
