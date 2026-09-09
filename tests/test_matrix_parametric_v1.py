"""End-to-end acceptance tests for the deliberately narrow Matrix V1 loop.

Every source raster in this module is created under a user-style filename and
is imported through ``PatternLabSession.import_image``.  The fixture menu is
not involved, so these tests prove that user images and system fixtures share
the same recognition and Grid fitting route.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from ppg.foundation import Canvas, FoundationPipeline, PatternDocument, Reference, SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.faithful_mapping import ConversionMode
from xiaomang_pattern_lab.parametric import (
    GridParametricModel,
    MaskMode,
    MaskModifier,
    PatternMode,
    SizeGradientMode,
    SizeGradientModifier,
)
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


def write_user_matrix(path: Path, model: GridParametricModel, *, missing: set[tuple[int, int]] | None = None) -> None:
    """Create a real PNG input, independent of Pattern Lab's fixture helper."""

    missing = missing or set()
    image = Image.new("L", (420, 420), "white")
    draw = ImageDraw.Draw(image)
    for index, element in enumerate(model.generate(include_overrides=False)):
        row, column = divmod(index, model.columns)
        if (row, column) in missing:
            continue
        draw.ellipse(
            (
                element.x - element.width / 2.0,
                element.y - element.height / 2.0,
                element.x + element.width / 2.0,
                element.y + element.height / 2.0,
            ),
            fill="black",
        )
    image.save(path)


class MatrixParametricV1Tests(unittest.TestCase):
    def test_real_user_png_cases_use_the_same_grid_analyzer(self) -> None:
        cases = {
            "用户A_12x12规则矩阵.png": (
                GridParametricModel(rows=12, columns=12, spacing_x=24, spacing_y=24, element_width=9, element_height=9, offset_x=210, offset_y=210),
                set(),
                (12, 12, 0.0),
            ),
            "用户B_8x18非方阵.png": (
                GridParametricModel(rows=8, columns=18, spacing_x=18, spacing_y=22, element_width=8, element_height=8, offset_x=210, offset_y=210),
                set(),
                (8, 18, 0.0),
            ),
            "用户C_15度旋转矩阵.png": (
                GridParametricModel(rows=7, columns=11, spacing_x=20, spacing_y=23, element_width=8, element_height=8, rotation=15, offset_x=210, offset_y=210),
                set(),
                (7, 11, 15.0),
            ),
            "用户D_尺寸渐变矩阵.png": (
                GridParametricModel(
                    rows=9, columns=13, spacing_x=22, spacing_y=22, element_width=8, element_height=8, offset_x=210, offset_y=210,
                    size_gradient=SizeGradientModifier(mode=SizeGradientMode.HORIZONTAL, min_size=4, max_size=12, strength=1),
                ),
                set(),
                (9, 13, 0.0),
            ),
            "用户E_缺少单元矩阵.png": (
                GridParametricModel(rows=12, columns=12, spacing_x=24, spacing_y=24, element_width=9, element_height=9, offset_x=210, offset_y=210),
                {(3, 5)},
                (12, 12, 0.0),
            ),
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for file_name, (model, missing, expected) in cases.items():
                source = root / file_name
                write_user_matrix(source, model, missing=missing)
                session = make_session(root / (source.stem + "-workspace"))
                document = session.import_image(str(source), ConversionMode.FAITHFUL)
                fit = session.analyze_pattern()
                self.assertIsNotNone(fit, file_name)
                self.assertEqual((fit.rows, fit.columns), expected[:2], file_name)
                self.assertAlmostEqual(fit.rotation, expected[2], delta=1.0, msg=file_name)
                self.assertGreaterEqual(fit.fit_score, 0.75, file_name)
                self.assertEqual(session.pattern_mode, PatternMode.FREE, file_name)
                if "尺寸渐变" in file_name:
                    self.assertIsNotNone(fit.gradient)
                    self.assertEqual(fit.gradient.modifier.mode, SizeGradientMode.HORIZONTAL)
                if "缺少单元" in file_name:
                    self.assertEqual(fit.missing_cell_count, 1)
                    session.activate_grid(fit.model)
                    self.assertFalse(session.document.element(fit.missing_cell_ids[0]).visible)
                # Imported source stays as real editable Free Elements until a
                # user explicitly confirms the conversion action.
                self.assertGreater(len(document.elements), 0)

    def test_evaluate_size_mask_override_bake_and_save_reload(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model = GridParametricModel(
                rows=7, columns=7, spacing_x=12, spacing_y=12, element_width=10, element_height=10,
                offset_x=100, offset_y=100,
                size_gradient=SizeGradientModifier(mode=SizeGradientMode.NONE),
                mask=MaskModifier(mode=MaskMode.CIRCLE, enabled=True, center_x=100, center_y=100, radius=23),
            )
            document = PatternDocument(Canvas(220, 220, "mm", 1.0), Reference("user-input.png", False), model.generate())
            session = PatternLabSession(FoundationPipeline(None, None), root / "workspace", document=document)
            session.activate_grid(model)
            self.assertTrue(session.document.metadata.get("xiaomang_pattern_lab.parametric", {}).get("source_elements"))
            self.assertEqual(len(session.evaluate_elements()), 49)
            self.assertLess(sum(item.visible for item in session.document.elements), 49)

            # The modifier is non-destructive: switching it off restores the
            # same cells without touching the base model or their stable ids.
            unmasked = GridParametricModel.from_dict(session.grid_model.to_dict())
            unmasked.mask.enabled = False
            session.update_grid(unmasked)
            self.assertEqual(sum(item.visible for item in session.document.elements), 49)

            target_id = GridParametricModel.element_id(3, 5)
            session.select(target_id)
            session.resize_selected(8.0, 8.0)  # 10 mm base × 0.8 override
            larger = GridParametricModel.from_dict(session.grid_model.to_dict())
            larger.element_width = larger.element_height = 12.0
            session.update_grid(larger)
            self.assertAlmostEqual(session.document.element(target_id).width, 9.6, places=5)

            # A hidden local override remains last in the evaluation order.
            session.select_many([GridParametricModel.element_id(0, 0), GridParametricModel.element_id(0, 1)])
            session.delete_selected()
            self.assertFalse(session.document.element(GridParametricModel.element_id(0, 0)).visible)
            self.assertFalse(session.document.element(GridParametricModel.element_id(0, 1)).visible)

            saved = session.save_document(str(root / "matrix-v1.pattern.json"))
            restored = PatternLabSession(FoundationPipeline(None, None), root / "restored")
            restored.load_document(str(saved))
            self.assertEqual(restored.pattern_mode, PatternMode.GRID)
            self.assertAlmostEqual(restored.document.element(target_id).width, 9.6, places=5)
            self.assertFalse(restored.document.element(GridParametricModel.element_id(0, 0)).visible)

            # Bake deliberately ends the parametric relationship but preserves
            # the exact evaluated geometry as independently editable Elements.
            before_bake = [(item.id, item.x, item.y, item.width, item.visible) for item in restored.document.elements]
            restored.bake_to_free_elements()
            self.assertEqual(restored.pattern_mode, PatternMode.FREE)
            self.assertNotIn("xiaomang_pattern_lab.parametric", restored.document.metadata)
            self.assertEqual([(item.id, item.x, item.y, item.width, item.visible) for item in restored.document.elements], before_bake)
            restored.select(target_id)
            duplicate = restored.duplicate_selected()
            self.assertNotEqual(duplicate, target_id)
            self.assertEqual(len(restored.document.elements), 50)

    def test_imported_path_mask_is_a_real_serializable_modifier(self) -> None:
        model = GridParametricModel(
            rows=5, columns=5, spacing_x=10, spacing_y=10, element_width=5, element_height=5,
            offset_x=20, offset_y=20,
            mask=MaskModifier(
                mode=MaskMode.IMPORTED_PATH, enabled=True,
                path_points=[(8, 8), (32, 8), (20, 34)],
            ),
        )
        visible = [element for element in model.generate() if element.visible]
        self.assertGreater(len(visible), 0)
        self.assertLess(len(visible), 25)
        restored = GridParametricModel.from_dict(model.to_dict())
        self.assertEqual(restored.mask.mode, MaskMode.IMPORTED_PATH)
        self.assertEqual(restored.mask.path_points, [(8.0, 8.0), (32.0, 8.0), (20.0, 34.0)])
        self.assertEqual([item.id for item in evaluate_pattern_document(PatternDocument(Canvas(80, 80, "mm", 1.0), Reference("", False), model.generate(), metadata={"xiaomang_pattern_lab.parametric": {"mode": "grid", "grid": model.to_dict()}}))], [item.id for item in model.generate()])

    def test_grid_multiselection_edits_are_one_transaction_and_survive_rebuild(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model = GridParametricModel(rows=4, columns=5, spacing_x=15, spacing_y=15, element_width=10, element_height=10, offset_x=60, offset_y=60)
            document = PatternDocument(Canvas(140, 140, "mm", 1.0), Reference("", False), model.generate())
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            session.activate_grid(model)
            first, second = GridParametricModel.element_id(1, 1), GridParametricModel.element_id(1, 2)
            before = {identifier: (session.document.element(identifier).x, session.document.element(identifier).y) for identifier in (first, second)}
            undo_before = session.undo_record_count
            session.select_many([first, second])
            session.move_selected(3.0, -2.0)
            self.assertEqual(session.undo_record_count, undo_before + 1)
            for identifier in (first, second):
                element = session.document.element(identifier)
                self.assertAlmostEqual(element.x, before[identifier][0] + 3.0)
                self.assertAlmostEqual(element.y, before[identifier][1] - 2.0)
            session.resize_selected(5.0, 5.0)
            self.assertAlmostEqual(session.document.element(first).width, 5.0)
            self.assertAlmostEqual(session.document.element(second).width, 5.0)
            replacement = GridParametricModel.from_dict(session.grid_model.to_dict())
            replacement.element_width = replacement.element_height = 12.0
            session.update_grid(replacement)
            # 5 / 10 local scale remains after a global base-size change.
            self.assertAlmostEqual(session.document.element(first).width, 6.0)
            self.assertAlmostEqual(session.document.element(second).width, 6.0)

    def test_previous_grid_id_format_migrates_without_losing_local_override(self) -> None:
        model = GridParametricModel(rows=2, columns=2, element_width=10, element_height=10)
        payload = model.to_dict()
        payload["local_overrides"] = {"grid-r1-c0": {"scale_x": 0.5, "scale_y": 0.5, "visible": False}}
        restored = GridParametricModel.from_dict(payload)
        identifier = "grid:r1:c0"
        self.assertIn(identifier, restored.local_overrides)
        element = {item.id: item for item in restored.generate()}[identifier]
        self.assertAlmostEqual(element.width, 5.0)
        self.assertFalse(element.visible)


if __name__ == "__main__":
    unittest.main()
