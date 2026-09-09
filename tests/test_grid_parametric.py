"""Headless proofs for the first Grid + SizeGradient parametric model."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ppg.foundation import Canvas, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.interaction import InteractionState
from xiaomang_pattern_lab.parametric import GridParametricModel, PatternMode, SizeGradientMode, SizeGradientModifier, infer_regular_grid
from xiaomang_pattern_lab.session import PatternLabSession


def make_grid(rows: int = 12, columns: int = 12) -> GridParametricModel:
    return GridParametricModel(
        rows=rows,
        columns=columns,
        spacing_x=11.0,
        spacing_y=13.0,
        element_width=5.0,
        element_height=5.0,
        offset_x=80.0,
        offset_y=90.0,
    )


class GridParametricTests(unittest.TestCase):
    def test_inference_measures_spatial_clusters_not_sqrt_count(self):
        model = make_grid(9, 16)
        measured = model.generate()
        measured[0].x += 1.25
        measured[0].width *= 1.4
        measured[0].height *= 1.4
        result = infer_regular_grid(measured)
        self.assertIsNotNone(result)
        self.assertEqual(result.model.rows, 9)
        self.assertEqual(result.model.columns, 16)
        # The measured first column was deliberately nudged; robust fitting
        # uses real cluster means rather than snapping coordinates to an ideal.
        self.assertAlmostEqual(result.model.spacing_x, 11.0, delta=0.02)
        self.assertAlmostEqual(result.model.spacing_y, 13.0, places=5)
        self.assertGreaterEqual(result.score, 0.95)
        recovered = {item.id: item for item in result.model.generate()}
        self.assertAlmostEqual(recovered["grid:r0:c0"].x, measured[0].x)
        self.assertAlmostEqual(recovered["grid:r0:c0"].width, measured[0].width)

    def test_center_to_edge_gradient_and_override_survive_grid_rebuild(self):
        model = make_grid(5, 5)
        model.size_gradient = SizeGradientModifier(
            mode=SizeGradientMode.CENTER_TO_EDGE, min_size=2.0, max_size=10.0, strength=1.0
        )
        generated = {item.id: item for item in model.generate()}
        self.assertLess(generated["grid:r2:c2"].width, generated["grid:r0:c0"].width)
        center = generated["grid:r2:c2"]
        with tempfile.TemporaryDirectory() as directory:
            document = PatternDocument(Canvas(200, 200, "mm", 1.0), Reference("reference.png", False), list(generated.values()))
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            session.activate_grid(model)
            session.select(center.id)
            with self.assertRaisesRegex(RuntimeError, "自由元素"):
                session.duplicate_selected()
            state = InteractionState(
                kind="move", element_id=center.id, handle=None,
                start_pointer_x=center.x, start_pointer_y=center.y,
                start_x=center.x, start_y=center.y, start_width=center.width, start_height=center.height, start_rotation=center.rotation,
                current_x=center.x + 7.5, current_y=center.y - 3.0,
                current_width=center.width * 1.2, current_height=center.height * 1.2, current_rotation=center.rotation,
            )
            session.begin_transaction("移动")
            self.assertTrue(session.commit_interaction(state))
            edited = session.document.element(center.id)
            self.assertAlmostEqual(edited.x, center.x + 7.5)
            self.assertAlmostEqual(edited.y, center.y - 3.0)
            # Change a base parameter: the local edit stays as a LocalOverride.
            next_model = GridParametricModel.from_dict(session.grid_model.to_dict())
            next_model.spacing_x = 16.0
            session.update_grid(next_model)
            rebuilt = session.document.element(center.id)
            base = session.grid_model.base_element(center.id)
            self.assertAlmostEqual(rebuilt.x - base.x, 7.5)
            self.assertAlmostEqual(rebuilt.y - base.y, -3.0)
            self.assertGreater(rebuilt.width, base.width)
            saved = session.save_document(str(Path(directory) / "grid.pattern.json"))
            restored = PatternLabSession(FoundationPipeline(None, None), Path(directory))
            restored.load_document(str(saved))
            self.assertEqual(restored.pattern_mode, PatternMode.GRID)
            self.assertIn(center.id, restored.grid_model.local_overrides)
            restored_item = restored.document.element(center.id)
            self.assertAlmostEqual(restored_item.x, rebuilt.x)
            self.assertAlmostEqual(restored_item.width, rebuilt.width)

    def test_pointer_motion_can_be_transient_for_three_thousand_elements(self):
        model = make_grid(50, 60)
        with tempfile.TemporaryDirectory() as directory:
            document = PatternDocument(Canvas(800, 800, "mm", 1.0), Reference("reference.png", False), model.generate())
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            first = document.elements[0]
            before = document.to_dict()
            session.begin_transaction("移动")
            state = InteractionState(
                kind="move", element_id=first.id, handle=None,
                start_pointer_x=first.x, start_pointer_y=first.y,
                start_x=first.x, start_y=first.y, start_width=first.width, start_height=first.height, start_rotation=first.rotation,
                current_x=first.x, current_y=first.y, current_width=first.width, current_height=first.height, current_rotation=first.rotation,
            )
            for step in range(240):
                state.set_position(first.x + step * 0.05, first.y + step * 0.025)
            # InteractionState alone changes; no document clone or SVG write.
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual(session.svg_serialize_count, 0)
            self.assertTrue(session.commit_interaction(state))
            self.assertEqual(session.svg_serialize_count, 1)
            self.assertEqual(session.undo_record_count, 1)


if __name__ == "__main__":
    unittest.main()
