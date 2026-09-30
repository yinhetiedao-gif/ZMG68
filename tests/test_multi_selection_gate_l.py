"""Gate L: one Selection source and non-destructive batch editing."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.interaction import InteractionState
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.placement_assignment import PlacementAssignmentState
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.ui_harness import PatternLabApp
from tests.tk_lifecycle import collect_tk_variables as tearDownModule


def make_document() -> PatternDocument:
    elements = [
        CircleElement("dot-%d" % index, (index % 3) * 20.0, (index // 3) * 20.0, 8, 8)
        for index in range(6)
    ]
    return PatternDocument(Canvas(100, 80, unit="mm", mm_per_unit=1.0), Reference(""), elements)


class MultiSelectionCoreTests(unittest.TestCase):
    def test_shift_rectangle_select_all_and_escape_are_one_session_selection_source(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document())
            session.select("dot-0")
            session.select("dot-1", additive=True)
            self.assertEqual(session.selected_ids, ["dot-0", "dot-1"])
            session.select("dot-1", additive=True)
            self.assertEqual(session.selected_ids, ["dot-0"])

            # The world-space rectangle has no dependence on canvas margin,
            # zoom or pan.  Shift + rectangle appends without duplicate IDs.
            session.select_rectangle(-1, -1, 21, 1)
            self.assertEqual(session.selected_ids, ["dot-0", "dot-1"])
            session.select_rectangle(-1, 19, 41, 41, additive=True)
            self.assertEqual(session.selected_ids, ["dot-0", "dot-1", "dot-3", "dot-4", "dot-5"])
            session.select_all()
            self.assertEqual(len(session.selected_ids), 6)
            session.clear_selection()
            self.assertEqual(session.selected_ids, [])
            self.assertIsNone(session.selected_id)

    def test_batch_move_scale_rotate_hide_show_and_undo_are_single_transactions(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document())
            session.select_many(["dot-0", "dot-1", "dot-3"])
            original = {item.id: (item.x, item.y, item.width, item.height, item.rotation) for item in session.document.elements}

            before = session.undo_record_count
            session.move_selected(5, -3)
            self.assertEqual(session.undo_record_count, before + 1)
            for identifier in session.selected_ids:
                current = session.document.element(identifier)
                self.assertEqual((current.x, current.y), (original[identifier][0] + 5, original[identifier][1] - 3))

            before = session.undo_record_count
            session.scale_selected(1.5, 1.5)
            self.assertEqual(session.undo_record_count, before + 1)
            self.assertEqual(session.document.element("dot-0").width, 12)
            self.assertEqual(session.document.element("dot-1").width, 12)

            before = session.undo_record_count
            session.rotate_selected_by(30)
            self.assertEqual(session.undo_record_count, before + 1)
            self.assertEqual(session.document.element("dot-3").rotation, 30)

            before = session.undo_record_count
            session.hide_selected()
            self.assertEqual(session.undo_record_count, before + 1)
            self.assertFalse(session.document.element("dot-0").visible)
            self.assertEqual(session.selected_ids, [])
            session.undo()
            self.assertTrue(session.document.element("dot-0").visible)
            session.redo()
            self.assertFalse(session.document.element("dot-0").visible)
            session.show_all_elements()
            self.assertTrue(all(element.visible for element in session.document.elements))

    def test_batch_replacement_group_drag_save_load_and_source_integrity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            source_before = deepcopy(session.document.elements)
            session.select_many(["dot-0", "dot-1", "dot-4"])
            before = session.undo_record_count
            session.replace_selected_shape("star")
            self.assertEqual(session.undo_record_count, before + 1)
            state = PlacementAssignmentState.from_document(session.document)
            self.assertEqual({key for key, value in state.replacement_map.values.items() if value == "star"}, {"dot-0", "dot-1", "dot-4"})
            self.assertEqual(state.source_snapshot(), source_before)

            # Canvas passes one transient primary interaction plus the chosen
            # IDs; the session commits the group delta exactly once.
            session.begin_transaction("移动")
            interaction = InteractionState(
                kind="move", element_id="dot-0", handle=None,
                start_pointer_x=0, start_pointer_y=0,
                start_x=session.document.element("dot-0").x,
                start_y=session.document.element("dot-0").y,
                start_width=session.document.element("dot-0").width,
                start_height=session.document.element("dot-0").height,
                start_rotation=session.document.element("dot-0").rotation,
                current_x=session.document.element("dot-0").x + 7,
                current_y=session.document.element("dot-0").y + 4,
                current_width=session.document.element("dot-0").width,
                current_height=session.document.element("dot-0").height,
                current_rotation=session.document.element("dot-0").rotation,
            )
            undo_before = session.undo_record_count
            session.commit_interaction(interaction, element_ids=list(session.selected_ids))
            self.assertEqual(session.undo_record_count, undo_before + 1)
            self.assertEqual((session.document.element("dot-1").x, session.document.element("dot-1").y), (27, 4))

            saved = session.save_document(root / "gate-l.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(restored.replacement_for("dot-4"), "star")
            self.assertEqual((restored.document.element("dot-1").x, restored.document.element("dot-1").y), (27, 4))
            svg = restored.export_svg(str(root / "gate-l.svg"))
            self.assertIn("<path", Path(svg).read_text(encoding="utf-8"))

            restored.select_many(["dot-0", "dot-1", "dot-4"])
            undo_before = restored.undo_record_count
            restored.restore_selected_shape()
            self.assertEqual(restored.undo_record_count, undo_before + 1)
            self.assertFalse(PlacementAssignmentState.from_document(restored.document).replacement_map.values)

    def test_grid_batch_visibility_and_rotation_survive_rebuild(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model = GridParametricModel(rows=2, columns=3, spacing_x=20, spacing_y=20, element_width=8)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            session.activate_grid(model)
            identifiers = ["grid:r0:c0", "grid:r0:c1"]
            session.select_many(identifiers)
            session.rotate_selected_by(45)
            self.assertEqual(session.document.element("grid:r0:c0").rotation, 45)
            session.hide_selected()
            self.assertFalse(session.document.element("grid:r0:c0").visible)
            session.show_all_elements()
            self.assertTrue(session.document.element("grid:r0:c0").visible)

    def test_selection_and_batch_editing_remain_bounded_at_100_to_1000_elements(self):
        with TemporaryDirectory() as directory:
            for count in (100, 500, 1000):
                elements = [CircleElement("dot-%d" % index, float(index % 50) * 4, float(index // 50) * 4, 2, 2) for index in range(count)]
                document = PatternDocument(Canvas(240, 100, "mm", 1.0), Reference(""), elements)
                session = PatternLabSession(FoundationPipeline(None, None), Path(directory) / str(count), document=document)
                started = perf_counter()
                session.select_rectangle(-1, -1, 300, 300)
                session.move_selected(1, 1)
                session.scale_selected(1.1, 1.1)
                elapsed = perf_counter() - started
                self.assertEqual(len(session.selected_ids), count)
                self.assertLess(elapsed, 3.0, "%d Elements batch edit took %.3fs" % (count, elapsed))


class MultiSelectionUITests(unittest.TestCase):
    def test_canvas_group_drag_commits_one_undo(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                app.update()
                first, second = app.session.document.elements[:2]
                app.session.select_many([first.id, second.id])
                app.refresh_canvas()
                start_x, start_y = app._view_transform.worldToScreen(first.x, first.y)
                before = {item.id: (item.x, item.y) for item in (first, second)}
                undo_before = app.session.undo_record_count
                app.canvas_press(SimpleNamespace(x=start_x, y=start_y, state=0))
                app.canvas_drag(SimpleNamespace(x=start_x + 24, y=start_y - 16, state=0))
                app.canvas_release(SimpleNamespace(x=start_x + 24, y=start_y - 16, state=0))
                dx, dy = app._view_transform.screenToWorld(start_x + 24, start_y - 16)
                origin_x, origin_y = app._view_transform.screenToWorld(start_x, start_y)
                for identifier in (first.id, second.id):
                    current = app.session.document.element(identifier)
                    self.assertAlmostEqual(current.x, before[identifier][0] + dx - origin_x)
                    self.assertAlmostEqual(current.y, before[identifier][1] + dy - origin_y)
                self.assertEqual(app.session.undo_record_count, undo_before + 1)
                app.undo()
                self.assertAlmostEqual(app.session.document.element(first.id).x, before[first.id][0])
            finally:
                app.destroy()

    def test_canvas_marquee_uses_world_coordinates_after_zoom_and_pan(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                app.update()
                transform = app._view_transform
                app.change_zoom(1.25)
                app._view_transform.pan_pixels(24, -12)
                transform = app._view_transform
                x0, y0 = transform.worldToScreen(10, 10)
                x1, y1 = transform.worldToScreen(90, 90)
                app.canvas_press(SimpleNamespace(x=x0, y=y0, state=0))
                app.canvas_drag(SimpleNamespace(x=x1, y=y1, state=0))
                app.canvas_release(SimpleNamespace(x=x1, y=y1, state=0))
                self.assertGreater(len(app.session.selected_ids), 0)
                selected_count = len(app.session.selected_ids)
                app.select_all_elements()
                self.assertEqual(len(app.session.selected_ids), len(app.session.document.elements))
                app.escape_selection()
                self.assertEqual(app.session.selected_ids, [])
                self.assertGreater(selected_count, 0)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
