"""Regression: the user's 13x13 raster-square image through every shared field.

This intentionally starts from the real JPG, not a hand-authored rectangle
document.  All cases share the same 169 imported FilledRegion elements.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

import numpy as np
from shapely.geometry import Polygon

from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.connectivity import ConnectivityAnalyzer
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.faithful_mapping import FaithfulMappingAdapter
from xiaomang_pattern_lab.geometry_validation import GeometryValidator
from xiaomang_pattern_lab.manufacturing_backend import TrimeshBackend
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.shared_fields import (
    CheckerField, ConstantField, FieldMapping, LinearField, NoiseField,
    RingField, SizeModifier, SpiralField, StripeField, WaveField,
)


FIXTURE = Path(__file__).parent / "fixtures" / "field_manufacturing_matrix_169.jpg"
FIELDS = {
    "constant": ConstantField("test", value=0.5),
    "linear": LinearField("test", angle=0),
    "wave": WaveField("test", wavelength=80),
    "ring": RingField("test", center_x=171.5, center_y=172, radius=90, ring_width=120),
    "stripe": StripeField("test", period=80),
    "checker": CheckerField("test", cell_width=50, cell_height=50),
    "spiral": SpiralField("test", center_x=171.5, center_y=172, turns=2),
    "noise": NoiseField("test", scale=80, seed=17),
}


def _shortest_edge(ring) -> float:
    lengths = [math.dist(start, end) for start, end in zip(ring, ring[1:] + ring[:1])]
    return min(lengths, default=math.inf)


class FieldManufacturingMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.document = FaithfulMappingAdapter(
            BinaryThresholdImageProcessingAdapter(),
            ImageToSVGVectorizationAdapter(mode="simple"),
        ).map_raster(str(FIXTURE), str(Path(cls.temporary.name) / "matrix.svg")).document
        cls.document.canvas.mm_per_unit = 1.0  # Web import's explicit provisional mapping.

    def test_all_shared_fields_manufacture_without_degenerate_faces(self) -> None:
        self.assertEqual(len(self.document.elements), 169)
        self.assertEqual({element.type for element in self.document.elements}, {"filled_region"})
        for name, field in (("none", None), *FIELDS.items()):
            with self.subTest(field=name):
                document = deepcopy(self.document)
                if field is not None:
                    document.fields = [field.to_dict()]
                    document.modifiers = [SizeModifier(
                        "size", "test", FieldMapping(min_output=0.8, max_output=1.0, strength=1.0),
                    ).to_dict()]
                stage = "evaluate"
                try:
                    final = evaluate_pattern_document(document)
                    stage = "Gate T"
                    geometry_report = GeometryValidator().validate_elements(final)
                    stage = "connectivity"
                    ConnectivityAnalyzer().analyze_elements(final, validation_report=geometry_report)
                    stage = "manufacturing adapter"
                    converted = ManufacturingGeometryAdapter().adapt_evaluated_document(
                        document, final, validation_report=geometry_report,
                    )
                    stage = "extrusion"
                    mesh = TrimeshBackend().extrude(converted.geometry, 2.0)
                    stage = "Mesh Validation"
                    report = MeshValidator().validate(mesh)
                except Exception as error:
                    self.fail(f"{name}: first failing stage={stage}: {type(error).__name__}: {error}")
                polygons = converted.geometry.polygons
                vertices, faces = mesh.mesh.vertices, mesh.mesh.faces
                face_areas = np.linalg.norm(np.cross(
                    vertices[faces[:, 1]] - vertices[faces[:, 0]],
                    vertices[faces[:, 2]] - vertices[faces[:, 0]],
                ), axis=1) / 2.0
                metrics = {
                    "field": name, "final_count": len(final),
                    "min_width": min(element.width for element in final),
                    "min_height": min(element.height for element in final),
                    "min_polygon_area": min(Polygon(item.outer).area for item in polygons),
                    "shortest_edge": min(_shortest_edge(item.outer) for item in polygons),
                    "gate_t_errors": geometry_report.error_count,
                    "adapter_skips": converted.report.skipped_count,
                    "vertices": len(vertices), "faces": len(faces),
                    "min_face_area": float(face_areas.min()),
                    "degenerate_faces": report.degenerate_face_count,
                    "mesh_errors": report.error_count,
                }
                print(metrics, flush=True)
                self.assertEqual(geometry_report.error_count, 0, metrics)
                self.assertEqual(converted.report.converted_count, 169, metrics)
                self.assertEqual(report.degenerate_face_count, 0, metrics)
                self.assertEqual(report.error_count, 0, metrics)


if __name__ == "__main__":
    unittest.main()
