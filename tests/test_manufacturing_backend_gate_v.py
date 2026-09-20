"""Gate V-MVP: Manufacturing2DGeometry → derived 3D mesh, without STL."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, RectElement, Reference
from xiaomang_pattern_lab.manufacturing_backend import TrimeshBackend
from xiaomang_pattern_lab.manufacturing_geometry import Manufacturing2DGeometry, ManufacturingPolygon
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession


def polygon(identifier: str, points, holes=()):
    return ManufacturingPolygon(identifier, tuple(points), tuple(tuple(hole) for hole in holes))


def geometry(*polygons):
    all_points = [point for item in polygons for point in item.outer]
    xs, ys = zip(*all_points)
    return Manufacturing2DGeometry(tuple(polygons), "mm", (min(xs), min(ys), max(xs), max(ys)))


def lab_document(elements):
    return PatternDocument(Canvas(200, 200, "mm", 1.0), Reference("", False), list(elements))


class ManufacturingBackendGateVTests(unittest.TestCase):
    def setUp(self):
        self.backend = TrimeshBackend()

    def test_rectangle_is_exactly_twenty_by_ten_by_two_mm(self):
        source = geometry(polygon("rect", ((0, 0), (20, 0), (20, 10), (0, 10))))
        result = self.backend.extrude(source, 2.0)
        self.assertEqual(result.bounds, ((0.0, 0.0, 0.0), (20.0, 10.0, 2.0)))
        self.assertEqual(result.size, (20.0, 10.0, 2.0))
        self.assertGreater(result.vertex_count, 0)
        self.assertGreater(result.face_count, 0)
        self.assertTrue(result.is_watertight)

    def test_circle_and_irregular_star_meshes_are_finite(self):
        circle = polygon("circle", tuple((5 * math.cos(index * 2 * math.pi / 32), 5 * math.sin(index * 2 * math.pi / 32)) for index in range(32)))
        star = polygon("star", ((0, 5), (1.6, 1.6), (5, 1.5), (2.4, -0.6), (3.5, -4.5), (0, -2.5), (-3.5, -4.5), (-2.4, -0.6), (-5, 1.5), (-1.6, 1.6)))
        result = self.backend.extrude(geometry(circle, star), 2)
        self.assertEqual(result.component_count, 2)
        self.assertTrue(np.isfinite(result.mesh.vertices).all())
        self.assertTrue(result.is_watertight)

    def test_polygon_hole_remains_through_the_full_two_mm_height(self):
        source = geometry(polygon(
            "plate", ((0, 0), (20, 0), (20, 20), (0, 20)),
            holes=(((6, 6), (14, 6), (14, 14), (6, 14)),),
        ))
        result = self.backend.extrude(source, 2)
        self.assertTrue(result.is_watertight)
        self.assertEqual(result.size, (20.0, 20.0, 2.0))
        # A filled top triangle inside the central 8×8 area would prove the
        # hole was silently capped.  Side faces do not satisfy all-z==top.
        faces = result.mesh.faces
        vertices = result.mesh.vertices
        top_faces = [face for face in faces if np.allclose(vertices[face, 2], 2.0)]
        for face in top_faces:
            x, y = vertices[face, :2].mean(axis=0)
            self.assertFalse(6.0 < x < 14.0 and 6.0 < y < 14.0)

    def test_disconnected_polygons_remain_two_bodies_without_bridge(self):
        source = geometry(
            polygon("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
            polygon("right", ((20, 0), (25, 0), (25, 5), (20, 5))),
        )
        result = self.backend.extrude(source, 2)
        self.assertEqual(result.component_count, 2)
        self.assertTrue(result.is_watertight)

    def test_touching_rectangles_have_no_created_gap_or_bridge(self):
        source = geometry(
            polygon("left", ((0, 0), (10, 0), (10, 10), (0, 10))),
            polygon("right", ((10, 0), (20, 0), (20, 10), (10, 10))),
        )
        result = self.backend.extrude(source, 2)
        self.assertEqual(result.component_count, 2)  # no Boolean union in V
        self.assertTrue(np.any(np.isclose(result.mesh.vertices[:, 0], 10.0)))
        self.assertEqual(result.size, (20.0, 10.0, 2.0))

    def test_zero_negative_nan_and_inf_height_are_rejected(self):
        source = geometry(polygon("rect", ((0, 0), (1, 0), (1, 1), (0, 1))))
        for height in (0, -1, math.nan, math.inf):
            with self.assertRaisesRegex(ValueError, "height_mm"):
                self.backend.extrude(source, height)

    def test_same_input_is_deterministic_and_not_mutated(self):
        source = geometry(polygon("rect", ((0, 0), (20, 0), (20, 10), (0, 10))))
        before = deepcopy(source)
        first = self.backend.extrude(source, 2)
        second = self.backend.extrude(source, 2)
        self.assertEqual(source, before)
        self.assertTrue(np.array_equal(first.mesh.vertices, second.mesh.vertices))
        self.assertTrue(np.array_equal(first.mesh.faces, second.mesh.faces))

    def test_real_pattern_lab_manufacturing_geometry_builds_read_only_mesh(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=12, spacing_y=12,
                                    element_width=8, element_height=8, offset_x=30, offset_y=30)
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=lab_document(model.generate()))
            session.activate_grid(model)
            before = deepcopy(session.document.to_dict())
            revision, undo_count = session.revision, session.undo_record_count
            built = session.build_manufacturing_mesh(height_mm=2, backend=self.backend)
            self.assertEqual(built.conversion.report.converted_count, 6)
            self.assertEqual(built.mesh_result.height_mm, 2.0)
            self.assertGreater(built.mesh_result.face_count, 0)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.undo_record_count), (revision, undo_count))

    def test_adapter_result_from_rectangle_is_extruded_without_design_type_access(self):
        item = RectElement("rect", 10, 5, 20, 10, style={"fill": "#000"})
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=lab_document([item]))
            converted = session.adapt_manufacturing_geometry()
            result = self.backend.extrude(converted.geometry, 2)
            self.assertEqual(result.size, (20.0, 10.0, 2.0))


if __name__ == "__main__":
    unittest.main()
