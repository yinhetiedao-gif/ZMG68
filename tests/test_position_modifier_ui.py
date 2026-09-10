"""Gate I-UI: productized Position/Deformation controls."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xiaomang_pattern_lab.shared_modifiers import PositionModifier, SharedModifierStack
from xiaomang_pattern_lab.ui_harness import POSITION_MODE_FIELDS, PatternLabApp


class PositionModifierUITests(unittest.TestCase):
    def test_each_mode_shows_only_its_effective_controls_and_semantic_ranges(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                expected = {
                    "offset": ("offset_x", "offset_y"),
                    "attractor": ("center_x", "center_y", "strength", "radius", "falloff"),
                    "repeller": ("center_x", "center_y", "strength", "radius", "falloff"),
                    "radial_push": ("center_x", "center_y", "amount", "radius", "falloff"),
                    "twist": ("center_x", "center_y", "angle", "strength", "radius", "falloff"),
                    "wave": ("angle", "wavelength", "phase", "amount", "center_x", "center_y", "strength", "radius", "falloff"),
                }
                self.assertEqual(POSITION_MODE_FIELDS, expected)
                for mode, keys in expected.items():
                    app._load_position_controls(PositionModifier(mode=mode))
                    app.update()
                    self.assertEqual(app._position_visible_keys, keys)
                    self.assertEqual(tuple(app._position_control_widgets), keys)
                app._load_position_controls(PositionModifier(mode="offset"))
                offset_scale, offset_entry = app._position_control_widgets["offset_x"]
                self.assertLess(float(offset_scale.cget("from")), 0.0)
                self.assertGreater(float(offset_scale.cget("to")), 0.0)
                offset_scale.set(12.5); app.update()
                self.assertAlmostEqual(float(offset_entry.get()), 12.5)
                app._load_position_controls(PositionModifier(mode="twist"))
                angle_scale = app._position_control_widgets["angle"][0]
                self.assertEqual(float(angle_scale.cget("from")), -180.0)
                self.assertEqual(float(angle_scale.cget("to")), 180.0)
                self.assertEqual(float(app._position_control_widgets["strength"][0].cget("to")), 100.0)
            finally:
                app.destroy()

    def test_preview_commit_mode_reset_undo_save_and_svg(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                app._load_position_controls(PositionModifier(mode="offset"))
                app._add_current_stack_layer("position")
                app.update()
                index = app._selected_stack_index()
                self.assertEqual(index, 0)
                stack = SharedModifierStack.from_document(app.session.document)
                source_before = deepcopy(stack.source_elements)
                document_before = app.session.document.to_dict()
                undo_before = app.session.undo_record_count

                # Slider/Entry motion uses a temporary evaluation and cannot
                # write PatternDocument or append Undo records.
                app.position_offset_x_var.set("7.25")
                app._run_position_preview()
                self.assertEqual(app.session.document.to_dict(), document_before)
                self.assertEqual(app.session.undo_record_count, undo_before)
                self.assertIsNotNone(app._preview_grid_elements)

                app._commit_position_controls()
                app.update()
                self.assertEqual(app.session.undo_record_count, undo_before + 1)
                stack = SharedModifierStack.from_document(app.session.document)
                self.assertEqual(stack.source_elements, source_before)
                self.assertAlmostEqual(stack.modifiers[0]["parameters"]["offset_x"], 7.25)

                # A mode switch is one normal edit; reset keeps that mode and
                # only restores the selected Position layer.
                switch_before = app.session.undo_record_count
                app.position_mode_display_var.set("扭曲")
                app._on_position_mode_selected()
                app.update()
                self.assertEqual(app.session.undo_record_count, switch_before + 1)
                self.assertEqual(app._position_visible_keys, POSITION_MODE_FIELDS["twist"])
                app.position_angle_var.set("75")
                app._commit_position_controls(); app.update()
                app._reset_stack_layer(); app.update()
                stack = SharedModifierStack.from_document(app.session.document)
                self.assertEqual(stack.modifiers[0]["parameters"]["mode"], "twist")
                self.assertAlmostEqual(stack.modifiers[0]["parameters"]["angle"], 30.0)
                app.undo(); app.update()
                stack = SharedModifierStack.from_document(app.session.document)
                self.assertAlmostEqual(stack.modifiers[0]["parameters"]["angle"], 75.0)
                app.redo(); app.update()
                stack = SharedModifierStack.from_document(app.session.document)
                self.assertAlmostEqual(stack.modifiers[0]["parameters"]["angle"], 30.0)

                project = app.session.save_document(root / "gate-i-ui.pattern.json")
                svg = app.session.export_svg(str(root / "gate-i-ui.svg"))
                self.assertTrue(Path(svg).is_file())
                saved_stack = deepcopy(stack.to_dict())
                app.session.load_document(str(project))
                self.assertEqual(SharedModifierStack.from_document(app.session.document).to_dict(), saved_stack)
                self.assertEqual(SharedModifierStack.from_document(app.session.document).source_elements, source_before)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
