"""Gate J: one shared, non-destructive Scope system for every Modifier."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from ppg.foundation import SVGNormalizer
from xiaomang_pattern_lab.parametric_families import RotationFieldModifier, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import (
    ModifierScope,
    ModifierScopeMode,
    PositionModifier,
    SharedModifierStack,
)
from xiaomang_pattern_lab.ui_harness import PatternLabApp, SCOPE_MODE_FIELDS
from tests.tk_lifecycle import collect_tk_variables as tearDownModule


def make_document():
    elements = [
        CircleElement("left", -10, 0, 4, 4),
        CircleElement("center", 0, 0, 4, 4),
        CircleElement("right", 10, 0, 4, 4),
        CircleElement("top", 0, 10, 4, 4),
    ]
    return PatternDocument(Canvas(80, 80), Reference(""), elements), elements


class ModifierScopeCoreTests(unittest.TestCase):
    def test_circle_rectangle_selected_and_invert_share_one_scope_contract(self):
        document, source = make_document()
        stack = SharedModifierStack(source_elements=source)
        stack.add_modifier(
            "size",
            SizeFieldModifier(min_scale=2, max_scale=2).to_dict(),
            modifier_id="wave-size",
            scope=ModifierScope(mode=ModifierScopeMode.CIRCLE, center_x=0, center_y=0, radius=1),
        )
        stack.add_modifier(
            "rotation",
            RotationFieldModifier(angle=30).to_dict(),
            modifier_id="spiral-rotation",
            scope=ModifierScope(mode=ModifierScopeMode.RECTANGLE, center_x=0, center_y=0, width=30, height=2),
        )
        stack.add_modifier(
            "position",
            PositionModifier(mode="twist", center_x=0, center_y=0, angle=90, radius=100).to_dict(),
            modifier_id="twist-selected",
            scope=ModifierScope(mode=ModifierScopeMode.SELECTED, selected_element_ids=["right"]),
        )
        stack.attach(document)
        source_snapshot = deepcopy(stack.source_elements)
        evaluated = {item.id: item for item in PatternLabSession(
            FoundationPipeline(None, None), Path("."), document=document,
        ).evaluate_elements()}

        self.assertEqual(evaluated["center"].width, 8)
        self.assertEqual(evaluated["left"].width, 4)
        self.assertEqual(evaluated["right"].width, 4)
        self.assertEqual(evaluated["top"].width, 4)
        self.assertEqual(evaluated["left"].rotation, 30)
        self.assertEqual(evaluated["center"].rotation, 30)
        self.assertEqual(evaluated["right"].rotation, 30)
        self.assertEqual(evaluated["top"].rotation, 0)
        self.assertAlmostEqual(evaluated["right"].x, 10 * math.cos(math.radians(81)), places=6)
        self.assertAlmostEqual(evaluated["right"].y, 10 * math.sin(math.radians(81)), places=6)
        self.assertEqual(SharedModifierStack.from_document(document).source_elements, source_snapshot)
        self.assertEqual(document.elements, source)

        inverted = ModifierScope(
            mode=ModifierScopeMode.RECTANGLE, center_x=0, center_y=0,
            width=30, height=2, invert=True,
        )
        self.assertFalse(inverted.contains(source[0]))
        self.assertTrue(inverted.contains(source[3]))

    def test_missing_scope_is_all_and_scope_survives_undo_save_load_svg(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document, source = make_document()
            # Simulate a pre-Gate-J layer record without a scope key.
            stack = SharedModifierStack(source_elements=source, modifiers=[{
                "id": "legacy-position", "type": "position", "enabled": True,
                "parameters": PositionModifier(mode="offset", offset_x=5).to_dict(),
            }])
            stack.attach(document)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            self.assertEqual([item.x for item in session.evaluate_elements()], [-5, 5, 15, 5])

            before = deepcopy(session.document.to_dict())
            undo_before = session.undo_record_count
            preview = session.preview_modifier_scope(0, ModifierScope(
                mode=ModifierScopeMode.SELECTED, selected_element_ids=["center"],
            ))
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual(session.undo_record_count, undo_before)
            self.assertEqual([item.x for item in preview], [-10, 5, 10, 0])

            selected_scope = ModifierScope(
                mode=ModifierScopeMode.SELECTED, selected_element_ids=["center"], invert=False,
            )
            session.update_modifier_scope(0, selected_scope)
            self.assertEqual(session.undo_record_count, undo_before + 1)
            self.assertEqual([item.x for item in session.evaluate_elements()], [-10, 5, 10, 0])
            session.undo()
            self.assertEqual([item.x for item in session.evaluate_elements()], [-5, 5, 15, 5])
            session.redo()
            self.assertEqual([item.x for item in session.evaluate_elements()], [-10, 5, 10, 0])

            saved = session.save_document(root / "gate-j.pattern.json")
            svg_path = session.export_svg(str(root / "gate-j.svg"))
            normalized = SVGNormalizer().normalize_file(str(svg_path))
            self.assertEqual([item.x for item in normalized.elements], [-10, 5, 10, 0])

            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            restored_stack = SharedModifierStack.from_document(restored.document)
            restored_scope = restored_stack.scope_for(0)
            self.assertEqual(restored_scope.mode, ModifierScopeMode.SELECTED)
            self.assertEqual(restored_scope.selected_element_ids, ["center"])
            self.assertEqual([item.x for item in restored.evaluate_elements()], [-10, 5, 10, 0])
            self.assertEqual(restored_stack.source_elements, SharedModifierStack.from_document(session.document).source_elements)


class ModifierScopeUITests(unittest.TestCase):
    def test_scope_panel_switches_fields_and_commits_one_undo(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                app._add_current_stack_layer("size")
                app.update()
                self.assertEqual(app._selected_stack_index(), 0)
                expected = {
                    "全部元素": (),
                    "当前选择": (),
                    "圆形区域": ("center_x", "center_y", "radius"),
                    "矩形区域": ("center_x", "center_y", "width", "height"),
                }
                for label, keys in expected.items():
                    app.scope_mode_display_var.set(label)
                    app._load_scope_controls(app._default_scope_for_mode(app._scope_mode()))
                    app.update()
                    self.assertEqual(tuple(app._scope_control_widgets), keys)
                self.assertEqual(SCOPE_MODE_FIELDS[ModifierScopeMode.CIRCLE.value], expected["圆形区域"])

                app.session.select(app.session.document.elements[0].id)
                before = app.session.undo_record_count
                app.scope_mode_display_var.set("当前选择")
                app._on_scope_mode_selected()
                app.update()
                self.assertEqual(app.session.undo_record_count, before + 1)
                scope = SharedModifierStack.from_document(app.session.document).scope_for(0)
                self.assertEqual(scope.mode, ModifierScopeMode.SELECTED)
                self.assertEqual(scope.selected_element_ids, [app.session.document.elements[0].id])

                document_before = deepcopy(app.session.document.to_dict())
                preview_undo = app.session.undo_record_count
                app.scope_mode_display_var.set("圆形区域")
                app._load_scope_controls(app._default_scope_for_mode(ModifierScopeMode.CIRCLE))
                app.scope_radius_var.set("20")
                app._run_scope_preview()
                self.assertEqual(app.session.document.to_dict(), document_before)
                self.assertEqual(app.session.undo_record_count, preview_undo)
                app._commit_scope_controls()
                app.update()
                self.assertEqual(app.session.undo_record_count, preview_undo + 1)
                self.assertEqual(
                    SharedModifierStack.from_document(app.session.document).scope_for(0).mode,
                    ModifierScopeMode.CIRCLE,
                )
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
