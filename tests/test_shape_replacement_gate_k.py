"""Gate K: single-element non-destructive Shape Replacement."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FilledRegionElement, FoundationPipeline, PatternDocument, RectElement, Reference
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.parametric_families import RotationFieldModifier, SizeFieldModifier
from xiaomang_pattern_lab.placement_assignment import (
    PLACEMENT_METADATA_KEY,
    PlacementAssignmentState,
    ShapePrototypeRegistry,
)
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import (
    ModifierScope,
    ModifierScopeMode,
    PositionModifier,
    SharedModifierStack,
)
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def make_document(count: int = 1) -> PatternDocument:
    elements = [CircleElement("dot-%d" % index, index * 10.0, 0, 8, 8) for index in range(count)]
    return PatternDocument(Canvas(100, 80, unit="mm", mm_per_unit=1.0), Reference(""), elements)


class ShapeReplacementCoreTests(unittest.TestCase):
    def test_builtins_are_normalized_and_all_required_replacements_restore(self):
        registry = ShapePrototypeRegistry.with_builtins()
        self.assertTrue({"circle", "square", "diamond", "triangle", "star", "line"}.issubset(registry.ids()))
        for name in ("diamond", "triangle", "star", "line"):
            prototype = registry.get(name)
            self.assertEqual((prototype.base_x, prototype.base_y), (0.0, 0.0))
            self.assertEqual((prototype.base_width, prototype.base_height), (1.0, 1.0))
            self.assertTrue(prototype.path_data.startswith("M "))

        with TemporaryDirectory() as directory:
            for name in ("star", "diamond", "triangle", "line"):
                session = PatternLabSession(FoundationPipeline(None, None), Path(directory) / name, document=make_document())
                session.select("dot-0")
                source_before = deepcopy(session.document.elements)
                session.replace_selected_shape(name)
                result = session.document.element("dot-0")
                self.assertIsInstance(result, FilledRegionElement, name)
                self.assertEqual((result.x, result.y, result.width, result.height, result.rotation), (0, 0, 8, 8, 0), name)
                state = PlacementAssignmentState.from_document(session.document)
                self.assertEqual(state.replacement_map.values["dot-0"], name)
                self.assertEqual(state.source_snapshot(), source_before)
                self.assertEqual(session.undo_record_count, 1)

                svg_path = session.export_svg(str(Path(directory) / (name + ".svg")))
                svg_text = Path(svg_path).read_text(encoding="utf-8")
                self.assertIn("<path", svg_text)
                self.assertNotIn("<circle", svg_text)

                session.restore_selected_shape()
                self.assertIsInstance(session.document.element("dot-0"), CircleElement)
                self.assertNotIn("dot-0", PlacementAssignmentState.from_document(session.document).replacement_map.values)
                self.assertEqual(PlacementAssignmentState.from_document(session.document).source_snapshot(), source_before)

    def test_replacement_composes_with_size_rotation_position_scope_and_direct_edit(self):
        document = make_document(3)
        source_before = deepcopy(document.elements)
        stack = SharedModifierStack(source_elements=document.elements)
        only_center = ModifierScope(mode=ModifierScopeMode.SELECTED, selected_element_ids=["dot-1"])
        stack.add_modifier("size", SizeFieldModifier(min_scale=2, max_scale=2).to_dict(), scope=only_center)
        stack.add_modifier("rotation", RotationFieldModifier(angle=25).to_dict(), scope=only_center)
        stack.add_modifier("position", PositionModifier(mode="offset", offset_x=3).to_dict(), scope=only_center)
        stack.attach(document)

        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        session = PatternLabSession(FoundationPipeline(None, None), Path(workspace.name), document=document)
        session.select("dot-1")
        session.replace_selected_shape("star")
        star = session.document.element("dot-1")
        self.assertIsInstance(star, FilledRegionElement)
        self.assertEqual((star.width, star.height, star.rotation, star.x), (16, 16, 25, 13))
        self.assertEqual((session.document.element("dot-0").width, session.document.element("dot-0").x), (8, 0))

        session.set_element_position("dot-1", 20, 5)
        moved = session.document.element("dot-1")
        # The replacement slot stays editable and the existing downstream
        # Position layer continues to apply after it.
        self.assertEqual((moved.x, moved.y), (23, 5))
        state = PlacementAssignmentState.from_document(session.document)
        slot = next(item for item in state.slots if item.slot_id == "dot-1")
        self.assertEqual((slot.center_x, slot.center_y), (20, 5))
        self.assertEqual(state.source_snapshot(), source_before)
        self.assertEqual(SharedModifierStack.from_document(session.document).source_snapshot(), source_before)

    def test_undo_redo_save_load_grid_update_svg_and_old_document_compatibility(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            session.select("dot-0")
            original_payload = deepcopy(session.document.to_dict())
            session.replace_selected_shape("diamond")
            self.assertIsInstance(session.document.element("dot-0"), FilledRegionElement)
            session.undo()
            self.assertEqual(session.document.to_dict(), original_payload)
            session.redo()
            self.assertIsInstance(session.document.element("dot-0"), FilledRegionElement)

            saved = session.save_document(root / "gate-k.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.replacement_for("dot-0"), "diamond")
            self.assertIsInstance(restored.document.element("dot-0"), FilledRegionElement)
            svg = restored.export_svg(str(root / "restored.svg"))
            self.assertIn("<path", Path(svg).read_text(encoding="utf-8"))

            grid_session = PatternLabSession(FoundationPipeline(None, None), root / "grid", document=make_document(4))
            grid_session.activate_grid(GridParametricModel(rows=2, columns=2, spacing_x=10, spacing_y=10, element_width=6))
            grid_session.select("grid:r0:c0")
            grid_session.replace_selected_shape("star")
            self.assertIsInstance(grid_session.document.element("grid:r0:c0"), FilledRegionElement)
            updated = GridParametricModel.from_dict(grid_session.grid_model.to_dict())
            updated.set_basis_vectors((20, 0), updated.basis_v)
            grid_session.update_grid(updated)
            self.assertIsInstance(grid_session.document.element("grid:r0:c0"), FilledRegionElement)
            self.assertEqual(grid_session.document.element("grid:r0:c1").x, 10)

            old = make_document()
            self.assertNotIn(PLACEMENT_METADATA_KEY, old.metadata)
            old_session = PatternLabSession(FoundationPipeline(None, None), root / "old", document=old)
            self.assertEqual(old_session.evaluate_elements(), old.elements)


class ShapeReplacementUITests(unittest.TestCase):
    def test_single_selection_chinese_ui_apply_and_restore(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                target = app.session.document.elements[0].id
                original_type = type(app.session.document.element(target))
                app.session.select(target)
                app.refresh_fields(force=True)
                self.assertEqual(app._current_shape_text.get(), "当前形状：原始")
                app.shape_replacement_display_var.set("星形")
                app.apply_shape_replacement(); app.update()
                self.assertEqual(app._current_shape_text.get(), "当前形状：星形")
                self.assertIsInstance(app.session.document.element(target), FilledRegionElement)
                app.restore_shape(); app.update()
                self.assertEqual(app._current_shape_text.get(), "当前形状：原始")
                self.assertIsInstance(app.session.document.element(target), original_type)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
