"""Regression coverage for multi-family parameterisation.

The assertions intentionally construct only real Foundation Elements.  No test
uses a filename, fixture identifier or Canvas state as recognition evidence.
"""
from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference

from tests.test_matrix_parametric_v1 import make_session
from xiaomang_pattern_lab.parametric import GridParametricModel, PatternMode
from xiaomang_pattern_lab.parametric_families import (
    AlongCurveParametricModel,
    FreeParametricModel,
    RadialParametricModel,
    RotationFieldMode,
    RotationFieldModifier,
    SizeFieldMode,
    SizeFieldModifier,
)
from xiaomang_pattern_lab.pattern_analyzer import PatternAnalyzer
from xiaomang_pattern_lab.session import PatternLabSession


def circle(identifier: str, x: float, y: float, size: float = 6.0) -> CircleElement:
    return CircleElement(id=identifier, x=x, y=y, width=size, height=size, style={"fill": "#000000"})


class MultiFamilyParametricTests(unittest.TestCase):
    def test_grid_remains_the_recommended_family(self) -> None:
        model = GridParametricModel(rows=6, columns=8, spacing_x=18, spacing_y=21, offset_x=70, offset_y=85)
        result = PatternAnalyzer().analyze_families(model.generate())
        self.assertEqual(result.recommended.family, "grid")
        self.assertGreaterEqual(result.candidate("grid").confidence, 0.75)

    def test_circular_radial_dots_are_recommended_as_radial(self) -> None:
        elements = [circle("source:%d" % index, 100 + cos(2 * pi * index / 12) * 52, 100 + sin(2 * pi * index / 12) * 52)
                    for index in range(12)]
        result = PatternAnalyzer().analyze_families(elements)
        self.assertIsNotNone(result.candidate("radial").model)
        self.assertEqual(result.recommended.family, "radial")
        radial = result.candidate("radial").fit
        self.assertAlmostEqual(radial.center_x, 100.0, delta=0.01)
        self.assertAlmostEqual(radial.center_y, 100.0, delta=0.01)

    def test_arc_and_s_curve_sequences_are_recognised_as_along_curve(self) -> None:
        arc = [circle("arc:%d" % index, 100 + cos(-1.2 + index * 0.2) * 75, 90 + sin(-1.2 + index * 0.2) * 75)
               for index in range(11)]
        arc_result = PatternAnalyzer().analyze_families(arc)
        self.assertIsNotNone(arc_result.candidate("along_curve").model)
        self.assertEqual(arc_result.recommended.family, "along_curve")

        s_curve = [circle("s:%d" % index, index * 15.0, 70 + 25 * sin(index * pi / 6.0)) for index in range(13)]
        s_result = PatternAnalyzer().analyze_families(s_curve)
        self.assertIsNotNone(s_result.candidate("along_curve").model)
        self.assertEqual(s_result.recommended.family, "along_curve")

    def test_irregular_geometry_has_a_free_parametric_fallback(self) -> None:
        elements = [circle("irregular:%d" % index, x, y, 4 + index) for index, (x, y) in enumerate(
            ((3, 7), (41, 96), (83, 12), (161, 57), (204, 154), (287, 35), (320, 226))
        )]
        result = PatternAnalyzer().analyze_families(elements)
        self.assertIsNone(result.recommended)
        self.assertEqual(result.fallback.family, "free")
        self.assertEqual(result.fallback.parameters["element_count"], len(elements))

    def test_free_fields_and_local_overrides_survive_save_reload(self) -> None:
        elements = [circle("e%d" % index, 20 + index * 20, 50, 5) for index in range(5)]
        document = PatternDocument(Canvas(180, 120, unit="mm", mm_per_unit=1.0), Reference(""), elements)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            free = FreeParametricModel.from_elements(elements)
            free.size_field = SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=0.5, max_scale=2.0)
            free.rotation_field = RotationFieldModifier(mode=RotationFieldMode.CONSTANT, angle=15.0)
            session.activate_free_parametric(free)
            original = session.document.element("e2")
            session.select("e2")
            session.move_selected(9, -4)
            saved = session.save_document(str(root / "free.pattern.json"))

            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.pattern_mode, PatternMode.FREE_PARAMETRIC)
            self.assertEqual(type(restored.parametric_model).__name__, "FreeParametricModel")
            self.assertAlmostEqual(restored.document.element("e2").x, original.x + 9)
            self.assertGreater(restored.document.element("e4").width, restored.document.element("e0").width)

    def test_along_curve_model_samples_later_equal_length_segments(self) -> None:
        model = AlongCurveParametricModel(path_points=[(0, 0), (10, 0), (20, 0)], count=3)
        generated = model.generate()
        self.assertEqual([(round(item.x), round(item.y)) for item in generated], [(0, 0), (10, 0), (20, 0)])

    def test_radial_local_override_and_mask_round_trip_through_session(self) -> None:
        base = RadialParametricModel(count=8, center_x=80, center_y=80, base_radius=35, end_radius=35)
        document = PatternDocument(Canvas(180, 180, unit="mm", mm_per_unit=1.0), Reference(""), base.generate())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            session.activate_radial(base)
            identifier = RadialParametricModel.element_id(3)
            original = session.document.element(identifier).y
            session.select(identifier)
            session.move_selected(-2, 8)
            saved = session.save_document(str(root / "radial.pattern.json"))
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.pattern_mode, PatternMode.RADIAL)
            self.assertAlmostEqual(restored.document.element(identifier).y, original + 8)


if __name__ == "__main__":
    unittest.main()
