"""Matrix Parameterization V2 acceptance tests.

Each raster case enters through ``PatternLabSession.import_image``.  The
custom-path case starts from a genuine SVG path and the shared normalizer—the
same Vector Geometry representation an SVG import route will use—so it proves
that a Grid prototype is not circle-specific.
"""
from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from ppg.foundation import SVGNormalizer
from xiaomang_pattern_lab.faithful_mapping import ConversionMode
from xiaomang_pattern_lab.parametric import GridParametricModel, PatternMode
from xiaomang_pattern_lab.pattern_analyzer import AnalysisTolerance, GridAnalyzer
from tests.test_matrix_parametric_v1 import make_session


def _world_point(cx: float, cy: float, row: int, column: int, *, rows: int, columns: int,
                 spacing_x: float, spacing_y: float, rotation: float) -> tuple[float, float]:
    local_x = (column - (columns - 1) / 2.0) * spacing_x
    local_y = (row - (rows - 1) / 2.0) * spacing_y
    radians = rotation * pi / 180.0
    return cx + local_x * cos(radians) - local_y * sin(radians), cy + local_x * sin(radians) + local_y * cos(radians)


def _star(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    return [(cx + cos(-pi / 2 + index * pi / 5) * (radius if index % 2 == 0 else radius * 0.45),
             cy + sin(-pi / 2 + index * pi / 5) * (radius if index % 2 == 0 else radius * 0.45)) for index in range(10)]


def write_shape_matrix(path: Path, *, shape: str, rows: int, columns: int, spacing_x: float,
                       spacing_y: float, center: tuple[float, float], rotation: float = 0.0,
                       y_gradient: bool = False, missing: set[tuple[int, int]] | None = None,
                       size: float = 9.0, canvas: tuple[int, int] = (1100, 850)) -> None:
    """Create user-style PNG input; no Pattern Lab fixture helper is involved."""

    missing = missing or set()
    image = Image.new("L", canvas, "white")
    draw = ImageDraw.Draw(image)
    for row in range(rows):
        for column in range(columns):
            if (row, column) in missing:
                continue
            x, y = _world_point(*center, row, column, rows=rows, columns=columns,
                                spacing_x=spacing_x, spacing_y=spacing_y, rotation=rotation)
            cell_size = size * (0.55 + 0.95 * row / max(1, rows - 1)) if y_gradient else size
            if shape == "circle":
                draw.ellipse((x - cell_size / 2, y - cell_size / 2, x + cell_size / 2, y + cell_size / 2), fill="black")
            elif shape == "diamond":
                draw.polygon([(x, y - cell_size / 2), (x + cell_size / 2, y), (x, y + cell_size / 2), (x - cell_size / 2, y)], fill="black")
            elif shape == "star":
                draw.polygon(_star(x, y, cell_size / 2), fill="black")
            else:
                raise ValueError(shape)
    image.save(path)


class MatrixParametricV2Tests(unittest.TestCase):
    def _import_fit(self, image: Path, workspace: Path, *, tolerance: AnalysisTolerance = AnalysisTolerance.STANDARD):
        session = make_session(workspace)
        session.import_image(str(image), ConversionMode.FAITHFUL)
        session.set_grid_analysis_tolerance(tolerance)
        return session, session.analyze_pattern()

    def test_star_and_diamond_user_pngs_become_custom_path_grids(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for shape in ("star", "diamond"):
                source = root / (shape + "-matrix.png")
                write_shape_matrix(source, shape=shape, rows=7, columns=11, spacing_x=38, spacing_y=42,
                                   center=(525, 410), y_gradient=True)
                session, fit = self._import_fit(source, root / (shape + "-workspace"))
                self.assertIsNotNone(fit, session.grid_analysis_debug)
                self.assertEqual((fit.rows, fit.columns), (7, 11))
                self.assertEqual(fit.prototype_kind, "custom_path")
                self.assertIsNotNone(fit.gradient)
                self.assertEqual(fit.gradient.modifier.mode.value, "vertical_y")
                session.activate_grid(fit.model)
                self.assertEqual(session.pattern_mode, PatternMode.GRID)
                self.assertTrue(all(item.type == "filled_region" for item in session.document.elements))
                # A Grid parameter rebuild may change placement but must not
                # replace the recovered path prototype with circles.
                replacement = GridParametricModel.from_dict(session.grid_model.to_dict())
                replacement.spacing_x += 3
                session.update_grid(replacement)
                self.assertTrue(all(item.type == "filled_region" for item in session.document.elements))
                target = GridParametricModel.element_id(3, 4)
                old_x = session.document.element(target).x
                session.select(target)
                session.move_selected(5.5, -2.0)
                self.assertAlmostEqual(session.document.element(target).x, old_x + 5.5)
                saved = session.save_document(str(root / (shape + "-matrix.pattern.json")))
                restored = make_session(root / (shape + "-restored"))
                restored.load_document(str(saved))
                self.assertEqual(restored.pattern_mode, PatternMode.GRID)
                self.assertEqual(restored.grid_model.prototype.kind, "custom_path")
                self.assertAlmostEqual(restored.document.element(target).x, old_x + 5.5)
                self.assertTrue(all(item.type == "filled_region" for item in restored.document.elements))

    def test_margin_missing_rotated_and_rectangular_rasters_use_centroids_not_canvas_bounds(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [
                ("large-margin.png", "circle", 8, 20, 26, 29, (700, 620), 0.0, set(), (1500, 1250)),
                ("missing-cells.png", "diamond", 9, 13, 38, 40, (500, 400), 0.0, {(2, 4), (6, 11)}, (1100, 850)),
                ("rotated.png", "star", 7, 12, 39, 43, (520, 400), 17.0, set(), (1100, 850)),
            ]
            for name, shape, rows, columns, sx, sy, center, rotation, missing, canvas in cases:
                source = root / name
                write_shape_matrix(source, shape=shape, rows=rows, columns=columns, spacing_x=sx, spacing_y=sy,
                                   center=center, rotation=rotation, missing=missing, canvas=canvas)
                session, fit = self._import_fit(source, root / (source.stem + "-workspace"), tolerance=AnalysisTolerance.STANDARD)
                self.assertIsNotNone(fit, session.grid_analysis_debug)
                self.assertEqual((fit.rows, fit.columns), (rows, columns), name)
                self.assertAlmostEqual(fit.rotation, rotation, delta=1.4, msg=name)
                self.assertGreaterEqual(fit.occupancy, 0.95 if not missing else 0.95 - len(missing) / (rows * columns) - 0.01)
                self.assertEqual(fit.missing_cell_count, len(missing), name)

    def test_custom_svg_path_matrix_prototype_round_trips_and_local_override_survives(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            svg = root / "custom-star-matrix.svg"
            paths = []
            for row in range(5):
                for column in range(8):
                    x, y = 80 + column * 34, 70 + row * 38
                    points = _star(x, y, 8)
                    d = "M " + " L ".join("%.2f %.2f" % point for point in points) + " Z"
                    paths.append('<path d="%s" fill="#000" stroke="none" />' % d)
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="300">%s</svg>' % "".join(paths), encoding="utf-8")
            document = SVGNormalizer().normalize_file(str(svg), reference_path=str(svg), normalization_mode="faithful")
            analyzer = GridAnalyzer(tolerance=AnalysisTolerance.STANDARD)
            fit = analyzer.analyze(document.elements)
            self.assertIsNotNone(fit, analyzer.last_debug)
            self.assertEqual((fit.rows, fit.columns), (5, 8))
            self.assertEqual(fit.prototype_kind, "custom_path")
            generated = fit.model.generate()
            self.assertTrue(all(item.type == "filled_region" for item in generated))
            identifier = fit.model.element_id(2, 3)
            fit.model.local_overrides[identifier].offset_x = 4.25
            restored = GridParametricModel.from_dict(fit.model.to_dict())
            self.assertEqual(restored.prototype.kind, "custom_path")
            self.assertAlmostEqual({item.id: item for item in restored.generate()}[identifier].x,
                                   {item.id: item for item in fit.model.generate()}[identifier].x)

    def test_analysis_debug_identifies_sparse_non_grid_without_losing_free_elements(self) -> None:
        model = GridParametricModel(rows=4, columns=4, spacing_x=20, spacing_y=20, offset_x=80, offset_y=80)
        elements = model.generate()
        # Break two positions beyond even the lenient spatial residual band.
        elements[-1].x += 67
        analyzer = GridAnalyzer(tolerance=AnalysisTolerance.STRICT)
        self.assertIsNone(analyzer.analyze(elements))
        self.assertGreater(analyzer.last_debug.candidate_count, 0)
        self.assertTrue(analyzer.last_debug.failure_reason)


if __name__ == "__main__":
    unittest.main()
