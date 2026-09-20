"""Gate W-Core: only inspect Gate V-derived Meshes; never repair or export."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.manufacturing_backend import ManufacturingMeshResult, TrimeshBackend
from xiaomang_pattern_lab.manufacturing_geometry import Manufacturing2DGeometry, ManufacturingPolygon
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession


@dataclass
class RawMesh:
    """Minimal fixture: no trimesh processing or repair can happen implicitly."""

    vertices: np.ndarray
    faces: np.ndarray


def result_for(vertices, faces) -> ManufacturingMeshResult:
    array = np.asarray(vertices, dtype=float)
    lower = np.nanmin(array, axis=0) if len(array) else np.zeros(3)
    upper = np.nanmax(array, axis=0) if len(array) else np.zeros(3)
    return ManufacturingMeshResult(
        mesh=RawMesh(array, np.asarray(faces)),
        bounds=(tuple(lower.tolist()), tuple(upper.tolist())),
        vertex_count=len(array), face_count=len(faces), component_count=0,
        height_mm=2.0, backend_name="raw-test", is_watertight=False,
    )


def polygon(identifier: str, points, holes=()):
    return ManufacturingPolygon(identifier, tuple(points), tuple(tuple(hole) for hole in holes))


def geometry(*polygons):
    points = [point for item in polygons for point in item.outer]
    xs, ys = zip(*points)
    return Manufacturing2DGeometry(tuple(polygons), "mm", (min(xs), min(ys), max(xs), max(ys)))


def lab_document(elements):
    return PatternDocument(Canvas(160, 160, "mm", 1.0), Reference("", False), list(elements))


class MeshValidationGateWCoreTests(unittest.TestCase):
    def setUp(self):
        self.backend = TrimeshBackend()
        self.validator = MeshValidator()

    def _valid_report(self, source):
        return self.validator.validate(self.backend.extrude(source, 2.0))

    def test_rectangle_circle_star_and_through_hole_are_valid(self):
        rectangle = geometry(polygon("rectangle", ((0, 0), (20, 0), (20, 10), (0, 10))))
        circle = geometry(polygon("circle", tuple((5 * math.cos(index * 2 * math.pi / 32), 5 * math.sin(index * 2 * math.pi / 32)) for index in range(32))))
        star = geometry(polygon("star", ((0, 5), (1.6, 1.6), (5, 1.5), (2.4, -0.6), (3.5, -4.5), (0, -2.5), (-3.5, -4.5), (-2.4, -0.6), (-5, 1.5), (-1.6, 1.6))))
        hole = geometry(polygon("hole", ((0, 0), (20, 0), (20, 20), (0, 20)), holes=(((6, 6), (14, 6), (14, 14), (6, 14)),)))
        for source in (rectangle, circle, star, hole):
            report = self._valid_report(source)
            self.assertTrue(report.is_valid)
            self.assertTrue(report.finite_coordinates)
            self.assertTrue(report.is_watertight)
            self.assertEqual(report.boundary_edge_count, 0)
            self.assertEqual(report.non_manifold_edge_count, 0)
            self.assertEqual(report.degenerate_face_count, 0)
            self.assertEqual(report.component_count, 1)

    def test_two_disconnected_mesh_bodies_are_valid_with_warning(self):
        source = geometry(
            polygon("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
            polygon("right", ((20, 0), (25, 0), (25, 5), (20, 5))),
        )
        report = self._valid_report(source)
        self.assertTrue(report.is_valid)
        self.assertTrue(report.is_watertight)
        self.assertEqual(report.component_count, 2)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(report.issues[0].issue_type, "multiple_components")

    def test_open_mesh_is_reported_as_non_watertight(self):
        # Tetrahedron with one surface omitted: three boundary edges remain.
        report = self.validator.validate(result_for(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
            ((0, 1, 2), (0, 3, 1), (1, 3, 2)),
        ))
        self.assertFalse(report.is_valid)
        self.assertFalse(report.is_watertight)
        self.assertGreater(report.boundary_edge_count, 0)
        self.assertTrue(any(issue.issue_type == "non_watertight" for issue in report.issues))

    def test_three_faces_on_one_edge_are_non_manifold(self):
        report = self.validator.validate(result_for(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0, -1, 0)),
            ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
        ))
        self.assertFalse(report.is_valid)
        self.assertGreater(report.non_manifold_edge_count, 0)
        self.assertTrue(any(issue.issue_type == "non_manifold_edges" for issue in report.issues))

    def test_collapsed_triangle_is_degenerate(self):
        report = self.validator.validate(result_for(
            ((0, 0, 0), (1, 0, 0), (2, 0, 0)), ((0, 1, 2),),
        ))
        self.assertFalse(report.is_valid)
        self.assertEqual(report.degenerate_face_count, 1)
        self.assertTrue(any(issue.issue_type == "degenerate_faces" for issue in report.issues))

    def test_non_finite_mesh_is_an_error_not_a_crash(self):
        report = self.validator.validate(result_for(
            ((0, 0, 0), (math.nan, 0, 0), (0, 1, 0)), ((0, 1, 2),),
        ))
        self.assertFalse(report.is_valid)
        self.assertFalse(report.finite_coordinates)
        self.assertTrue(any(issue.issue_type == "non_finite_coordinates" for issue in report.issues))

    def test_validation_is_read_only_and_deterministic(self):
        built = self.backend.extrude(geometry(polygon("rect", ((0, 0), (20, 0), (20, 10), (0, 10)))), 2)
        vertices = built.mesh.vertices.copy()
        faces = built.mesh.faces.copy()
        bounds = deepcopy(built.bounds)
        first = self.validator.validate(built)
        second = self.validator.validate(built)
        self.assertTrue(np.array_equal(built.mesh.vertices, vertices))
        self.assertTrue(np.array_equal(built.mesh.faces, faces))
        self.assertEqual(built.bounds, bounds)
        self.assertEqual(first, second)

    def test_real_pattern_lab_mesh_is_valid_and_session_state_is_read_only(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=12, spacing_y=12,
                                    element_width=8, element_height=8, offset_x=30, offset_y=30)
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(
                FoundationPipeline(None, None), Path(temporary), document=lab_document(model.generate()),
            )
            session.activate_grid(model)
            before = deepcopy(session.document.to_dict())
            revision, undo_count = session.revision, session.undo_record_count
            built = session.build_manufacturing_mesh(height_mm=2, backend=self.backend)
            report = session.validate_manufacturing_mesh(built.mesh_result, validator=self.validator)
            self.assertTrue(report.is_valid)
            self.assertEqual(report.component_count, 6)
            self.assertEqual(report.degenerate_face_count, 0)
            self.assertEqual(report.non_manifold_edge_count, 0)
            self.assertTrue(report.is_watertight)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.undo_record_count), (revision, undo_count))

    def test_gate_v_dependencies_are_importable(self):
        import mapbox_earcut  # noqa: F401
        import shapely  # noqa: F401
        import trimesh  # noqa: F401


if __name__ == "__main__":
    unittest.main()
