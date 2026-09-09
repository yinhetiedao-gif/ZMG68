"""Regression tests for user imports, renderer diagnostics and Grid fitting."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from ppg.foundation import FoundationPipeline, SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.faithful_mapping import ConversionMode
from xiaomang_pattern_lab.fixtures import build_fixed_suite
from xiaomang_pattern_lab.parametric import GridParametricModel, PatternMode, SizeGradientMode, SizeGradientModifier
from xiaomang_pattern_lab.pattern_analyzer import PatternAnalyzer
from xiaomang_pattern_lab.session import PatternLabSession


def make_session(workspace: Path) -> PatternLabSession:
    return PatternLabSession(
        FoundationPipeline(
            BinaryThresholdImageProcessingAdapter(),
            ImageToSVGVectorizationAdapter(mode="simple"),
            SVGNormalizer(),
        ),
        workspace,
    )


class PatternAnalyzerImportTests(unittest.TestCase):
    def test_star_halftone_has_no_nonrenderable_placeholder_geometry(self) -> None:
        fixtures = build_fixed_suite()
        with tempfile.TemporaryDirectory() as directory:
            session = make_session(Path(directory))
            document = session.import_image(str(fixtures["star_halftone"]), ConversionMode.PARAMETRIC)
            debug = session.debug_summary()
            self.assertEqual(len(document.elements), 63)
            self.assertEqual(debug.detected_element_count, 63)
            self.assertEqual(debug.renderable_element_count, 63)
            self.assertEqual(debug.visible_filled_element_count, 63)
            self.assertEqual(debug.invalid_geometry_count, 0)
            self.assertEqual(debug.unknown_primitive_count, 0)
            self.assertEqual({element.type for element in document.elements}, {"circle", "ellipse"})

    def test_user_png_import_uses_document_only_grid_analysis_and_rebuild(self) -> None:
        fixtures = build_fixed_suite()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # This uses a user-style filename and the public import method,
            # never the fixture selector or a preset id.
            user_png = root / "客户导入_规则点阵.png"
            shutil.copyfile(fixtures["regular_dot_matrix"], user_png)
            session = make_session(root / "workspace")
            document = session.import_image(str(user_png), ConversionMode.FAITHFUL)
            fit = session.analyze_pattern()
            self.assertIsNotNone(fit)
            self.assertEqual((fit.rows, fit.columns), (12, 12))
            self.assertAlmostEqual(fit.spacing_x, 24.0, delta=0.1)
            self.assertAlmostEqual(fit.spacing_y, 24.0, delta=0.1)
            self.assertGreaterEqual(fit.fit_score, 0.95)
            self.assertEqual(document.metadata.get("mapping_mode"), "faithful")

            session.activate_grid(fit.model)
            self.assertEqual(session.pattern_mode, PatternMode.GRID)
            self.assertEqual(len(session.document.elements), 144)
            replacement = GridParametricModel.from_dict(session.grid_model.to_dict())
            replacement.rows, replacement.columns = 10, 14
            replacement.spacing_x, replacement.spacing_y = 19.0, 21.0
            session.update_grid(replacement)
            self.assertEqual(len(session.document.elements), 140)
            self.assertEqual((session.grid_model.rows, session.grid_model.columns), (10, 14))

            selected = session.document.elements[0]
            session.select(selected.id)
            session.move_selected(3.0, -2.0)
            override_before = session.grid_model.local_overrides[selected.id].to_dict()
            project = session.save_document(str(root / "user-grid.pattern.json"))
            restored = make_session(root / "restored")
            restored.load_document(str(project))
            self.assertEqual(restored.pattern_mode, PatternMode.GRID)
            self.assertEqual(restored.grid_model.local_overrides[selected.id].to_dict(), override_before)

    def test_user_gradient_import_remains_editable_when_gradient_is_not_reliable(self) -> None:
        fixtures = build_fixed_suite()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_png = root / "客户导入_渐变半调.png"
            shutil.copyfile(fixtures["size_gradient_dot_matrix"], user_png)
            session = make_session(root / "workspace")
            document = session.import_image(str(user_png), ConversionMode.PARAMETRIC)
            fit = session.analyze_pattern()
            self.assertIsNotNone(fit)
            # V3 may now identify the diagonal field as a Radial/Elliptical
            # SizeField.  Whether it is fitted or left as local overrides,
            # the original imported Geometry must remain independently
            # editable after conversion.
            if fit.gradient is not None:
                self.assertIn(fit.gradient.modifier.mode, (SizeGradientMode.RADIAL, SizeGradientMode.ELLIPTICAL_RADIAL))
            session.activate_grid(fit.model)
            self.assertEqual(session.pattern_mode, PatternMode.GRID)
            self.assertTrue(session.grid_model.local_overrides)
            session.deactivate_grid()
            self.assertEqual(session.pattern_mode, PatternMode.FREE)
            self.assertEqual(len(session.document.elements), 144)

    def test_size_gradient_analyzer_selects_each_supported_mode(self) -> None:
        analyzer = PatternAnalyzer()
        for mode in (
            SizeGradientMode.HORIZONTAL,
            SizeGradientMode.VERTICAL,
            SizeGradientMode.CENTER_TO_EDGE,
            SizeGradientMode.EDGE_TO_CENTER,
        ):
            model = GridParametricModel(
                rows=7, columns=9, spacing_x=10.0, spacing_y=12.0,
                element_width=5.0, element_height=5.0, offset_x=80.0, offset_y=90.0,
                size_gradient=SizeGradientModifier(mode=mode, min_size=2.0, max_size=11.0, strength=1.0),
            )
            fit = analyzer.analyze(model.generate())
            self.assertIsNotNone(fit, mode.value)
            self.assertIsNotNone(fit.gradient, mode.value)
            self.assertEqual(fit.gradient.modifier.mode, mode)
            self.assertLess(fit.gradient.residual_error, 0.001)

    def test_sparse_star_keeps_free_elements_when_grid_score_is_not_reliable(self) -> None:
        fixtures = build_fixed_suite()
        with tempfile.TemporaryDirectory() as directory:
            session = make_session(Path(directory))
            document = session.import_image(str(fixtures["star_halftone"]), ConversionMode.FAITHFUL)
            self.assertIsNone(session.analyze_pattern())
            self.assertEqual(session.pattern_mode, PatternMode.FREE)
            first = document.elements[0]
            original_x = first.x
            session.select(first.id)
            session.move_selected(4.0, -3.0)
            self.assertAlmostEqual(session.document.element(first.id).x, original_x + 4.0)


if __name__ == "__main__":
    unittest.main()
