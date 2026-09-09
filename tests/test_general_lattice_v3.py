"""Acceptance tests for Matrix Parameterization V3.

These cases deliberately enter through the same user image/SVG import paths as
the application.  They prove that a matrix is fitted from Element centres and
two basis vectors, rather than from axis-aligned coordinates, canvas bounds,
or matching dot sizes.
"""
from __future__ import annotations

from math import hypot
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from ppg.foundation import SVGNormalizer
from xiaomang_pattern_lab.faithful_mapping import ConversionMode
from xiaomang_pattern_lab.parametric import GridParametricModel, LocalOverride, SizeGradientMode
from xiaomang_pattern_lab.pattern_analyzer import AnalysisTolerance, GridAnalyzer
from tests.test_matrix_parametric_v1 import make_session


def _point(origin: tuple[float, float], basis_u: tuple[float, float], basis_v: tuple[float, float], row: int, column: int) -> tuple[float, float]:
    return (
        origin[0] + column * basis_u[0] + row * basis_v[0],
        origin[1] + column * basis_u[1] + row * basis_v[1],
    )


def write_skew_dot_matrix(path: Path, *, rows: int = 8, columns: int = 12,
                          origin: tuple[float, float] = (240, 170),
                          basis_u: tuple[float, float] = (28, 9),
                          basis_v: tuple[float, float] = (-3, 31),
                          missing: set[tuple[int, int]] | None = None,
                          canvas: tuple[int, int] = (1050, 820)) -> None:
    """Make a cropped-looking, diagonal user PNG with a true 2D lattice."""
    image = Image.new("L", canvas, "white")
    draw = ImageDraw.Draw(image)
    missing = missing or set()
    center = _point(origin, basis_u, basis_v, (rows - 1) // 2, (columns - 1) // 2)
    for row in range(rows):
        for column in range(columns):
            if (row, column) in missing:
                continue
            x, y = _point(origin, basis_u, basis_v, row, column)
            # A deliberately strong elliptical field: Grid fitting may not use
            # this value; SizeField fitting may model it afterwards.
            dx, dy = (x - center[0]) / 250.0, (y - center[1]) / 165.0
            diameter = 5.0 + 15.0 * max(0.0, 1.0 - (dx * dx + dy * dy) ** 0.5)
            draw.ellipse((x - diameter / 2, y - diameter / 2, x + diameter / 2, y + diameter / 2), fill="black")
    image.save(path)


class GeneralLatticeV3Tests(unittest.TestCase):
    def test_imported_skew_gradient_lattice_uses_two_non_orthogonal_bases(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "user-skew-gradient.png"
            missing = {(1, 5), (5, 8), (6, 2)}
            write_skew_dot_matrix(source, missing=missing)
            session = make_session(root / "workspace")
            session.import_image(str(source), ConversionMode.FAITHFUL)
            session.set_grid_analysis_tolerance(AnalysisTolerance.LENIENT)
            fit = session.analyze_pattern()
            self.assertIsNotNone(fit, session.grid_analysis_debug)
            self.assertEqual((fit.rows, fit.columns), (8, 12))
            self.assertEqual(fit.missing_cell_count, len(missing))
            self.assertGreater(fit.occupancy, 0.94)
            self.assertGreater(abs(fit.basis_u[0] * fit.basis_v[1] - fit.basis_u[1] * fit.basis_v[0]), 100.0)
            # It is skewed, not merely a rotated rectangular grid.
            cosine = abs((fit.basis_u[0] * fit.basis_v[0] + fit.basis_u[1] * fit.basis_v[1]) / (hypot(*fit.basis_u) * hypot(*fit.basis_v)))
            self.assertGreater(cosine, 0.10)
            self.assertGreater(fit.debug.position_score, 0.85)
            self.assertGreater(fit.debug.inlier_ratio, 0.90)
            self.assertIsNotNone(fit.gradient)
            self.assertIn(fit.gradient.modifier.mode, (SizeGradientMode.RADIAL, SizeGradientMode.ELLIPTICAL_RADIAL))
            session.activate_grid(fit.model)
            self.assertEqual(session.grid_model.basis_u_vector, fit.model.basis_u_vector)
            self.assertEqual(session.grid_model.basis_v_vector, fit.model.basis_v_vector)

    def test_explicit_lattice_basis_round_trips_with_mask_and_local_override(self) -> None:
        model = GridParametricModel(
            rows=5, columns=9, offset_x=320, offset_y=250,
            element_width=9, element_height=9,
            basis_u_vector=(27.0, 8.0), basis_v_vector=(-7.0, 29.0),
        ).normalized()
        model.size_gradient.mode = SizeGradientMode.ELLIPTICAL_RADIAL
        model.size_gradient.min_size = 3.0
        model.size_gradient.max_size = 13.0
        model.size_gradient.center_x = 320.0
        model.size_gradient.center_y = 250.0
        model.size_gradient.radius_x = 140.0
        model.size_gradient.radius_y = 100.0
        identifier = model.element_id(2, 4)
        model.local_overrides[identifier] = LocalOverride(offset_x=4.0, scale_x=1.25)
        restored = GridParametricModel.from_dict(model.to_dict())
        self.assertEqual(restored.basis_u_vector, (27.0, 8.0))
        self.assertEqual(restored.basis_v_vector, (-7.0, 29.0))
        self.assertEqual(restored.size_gradient.mode, SizeGradientMode.ELLIPTICAL_RADIAL)
        self.assertAlmostEqual(restored.local_overrides[identifier].offset_x, 4.0)
        self.assertAlmostEqual(restored.local_overrides[identifier].scale_x, 1.25)

    def test_custom_svg_skewed_path_matrix_does_not_need_raster_or_canvas_alignment(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for row in range(6):
                for column in range(10):
                    x, y = _point((110, 80), (31, 11), (-9, 27), row, column)
                    paths.append('<path d="M %.1f %.1f l 6 4 l -6 4 l -6 -4 Z" fill="#000" stroke="none"/>' % (x, y - 4))
            svg = root / "skew-custom.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">%s</svg>' % ''.join(paths), encoding="utf-8")
            document = SVGNormalizer().normalize_file(str(svg), reference_path=str(svg), normalization_mode="faithful")
            fit = GridAnalyzer(tolerance=AnalysisTolerance.STANDARD).analyze(document.elements)
            self.assertIsNotNone(fit)
            self.assertEqual((fit.rows, fit.columns), (6, 10))
            self.assertEqual(fit.prototype_kind, "custom_path")
            self.assertNotAlmostEqual(abs(fit.rotation), 0.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
