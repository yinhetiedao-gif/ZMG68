"""Gate X: Gate W-gated, Binary STL export and faithful readback checks."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ppg.foundation import Canvas, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.manufacturing_backend import ManufacturingMeshResult, TrimeshBackend
from xiaomang_pattern_lab.manufacturing_geometry import Manufacturing2DGeometry, ManufacturingPolygon
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExportBlockedError, STLExporter


@dataclass
class RawMesh:
    vertices: np.ndarray
    faces: np.ndarray


def raw_result(vertices, faces) -> ManufacturingMeshResult:
    vertex_array = np.asarray(vertices, dtype=float)
    lower = np.nanmin(vertex_array, axis=0) if len(vertex_array) else np.zeros(3)
    upper = np.nanmax(vertex_array, axis=0) if len(vertex_array) else np.zeros(3)
    return ManufacturingMeshResult(
        mesh=RawMesh(vertex_array, np.asarray(faces)),
        bounds=(tuple(lower.tolist()), tuple(upper.tolist())),
        vertex_count=len(vertex_array), face_count=len(faces), component_count=0,
        height_mm=2, backend_name="raw-test", is_watertight=False,
    )


def polygon(identifier: str, points, holes=()):
    return ManufacturingPolygon(identifier, tuple(points), tuple(tuple(hole) for hole in holes))


def geometry(*polygons):
    points = [point for item in polygons for point in item.outer]
    xs, ys = zip(*points)
    return Manufacturing2DGeometry(tuple(polygons), "mm", (min(xs), min(ys), max(xs), max(ys)))


def lab_document(elements):
    return PatternDocument(Canvas(160, 160, "mm", 1.0), Reference("", False), list(elements))


class STLExportGateXTests(unittest.TestCase):
    def setUp(self):
        self.backend = TrimeshBackend()
        self.validator = MeshValidator()
        self.exporter = STLExporter(validator=self.validator)

    def _export_and_reload(self, source, filename="model.stl"):
        with tempfile.TemporaryDirectory() as temporary:
            original = self.backend.extrude(source, 2)
            target = Path(temporary) / filename
            exported = self.exporter.export(original, target)
            reloaded = self.exporter.reload_as_mesh_result(target)
            return exported, self.validator.validate(reloaded), reloaded

    def test_binary_rectangle_round_trip_stays_twenty_by_ten_by_two_mm(self):
        source = geometry(polygon("rect", ((0, 0), (20, 0), (20, 10), (0, 10))))
        exported, report, reloaded = self._export_and_reload(source)
        self.assertEqual(exported.format, "binary_stl")
        self.assertEqual(exported.units_assumption, "mm")
        self.assertGreater(exported.file_size_bytes, 84)
        self.assertEqual(reloaded.bounds, ((0.0, 0.0, 0.0), (20.0, 10.0, 2.0)))
        self.assertEqual((20.0, 10.0, 2.0), tuple(reloaded.bounds[1][index] - reloaded.bounds[0][index] for index in range(3)))
        self.assertTrue(report.is_valid)
        self.assertTrue(report.is_watertight)
        self.assertEqual(report.component_count, 1)

    def test_through_hole_survives_binary_stl_round_trip(self):
        source = geometry(polygon(
            "plate", ((0, 0), (20, 0), (20, 20), (0, 20)),
            holes=(((6, 6), (14, 6), (14, 14), (6, 14)),),
        ))
        exported, report, reloaded = self._export_and_reload(source, "hole.stl")
        self.assertTrue(report.is_valid)
        self.assertTrue(report.is_watertight)
        vertices, faces = reloaded.mesh.vertices, reloaded.mesh.faces
        for face in faces:
            if np.allclose(vertices[face, 2], 2.0):
                x, y = vertices[face, :2].mean(axis=0)
                self.assertFalse(6.0 < x < 14.0 and 6.0 < y < 14.0)
        self.assertEqual(exported.component_count, 1)

    def test_multi_component_stl_is_allowed_and_warning_is_preserved(self):
        source = geometry(
            polygon("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
            polygon("right", ((20, 0), (25, 0), (25, 5), (20, 5))),
        )
        exported, report, _reloaded = self._export_and_reload(source, "multi.stl")
        self.assertEqual(exported.component_count, 2)
        self.assertIn("multiple_disconnected_components", exported.warnings)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.component_count, 2)

    def test_gate_w_errors_block_before_any_stl_file_is_written(self):
        invalid_results = (
            raw_result(((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), ((0, 1, 2), (0, 3, 1), (1, 3, 2))),
            raw_result(((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0, -1, 0)), ((0, 1, 2), (1, 0, 3), (0, 1, 4))),
            raw_result(((0, 0, 0), (1, 0, 0), (2, 0, 0)), ((0, 1, 2),)),
            raw_result(((0, 0, 0), (math.nan, 0, 0), (0, 1, 0)), ((0, 1, 2),)),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for index, invalid in enumerate(invalid_results):
                target = Path(temporary) / ("invalid-%d.stl" % index)
                with self.assertRaises(STLExportBlockedError) as raised:
                    self.exporter.export(invalid, target)
                self.assertGreater(raised.exception.report.error_count, 0)
                self.assertFalse(target.exists())

    def test_export_does_not_mutate_source_mesh_and_requires_explicit_overwrite(self):
        source = geometry(polygon("rect", ((0, 0), (20, 0), (20, 10), (0, 10))))
        original = self.backend.extrude(source, 2)
        vertices, faces, bounds = original.mesh.vertices.copy(), original.mesh.faces.copy(), deepcopy(original.bounds)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "existing.stl"
            first = self.exporter.export(original, target)
            initial_bytes = target.read_bytes()
            with self.assertRaises(FileExistsError):
                self.exporter.export(original, target)
            self.assertEqual(target.read_bytes(), initial_bytes)
            second = self.exporter.export(original, target, overwrite=True)
        self.assertTrue(np.array_equal(original.mesh.vertices, vertices))
        self.assertTrue(np.array_equal(original.mesh.faces, faces))
        self.assertEqual(original.bounds, bounds)
        self.assertEqual(first.file_size_bytes, second.file_size_bytes)

    def test_real_pattern_lab_pipeline_exports_and_reloads_without_document_mutation(self):
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
            exported = session.export_validated_stl(built.mesh_result, Path(temporary) / "real-pattern.stl")
            report = self.validator.validate(self.exporter.reload_as_mesh_result(exported.output_path))
            self.assertGreater(exported.file_size_bytes, 84)
            self.assertEqual(exported.component_count, 6)
            self.assertIn("multiple_disconnected_components", exported.warnings)
            self.assertTrue(report.is_valid)
            self.assertEqual(report.component_count, 6)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.undo_record_count), (revision, undo_count))


if __name__ == "__main__":
    unittest.main()
