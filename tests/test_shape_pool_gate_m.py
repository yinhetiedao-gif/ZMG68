"""Gate M: deterministic, non-destructive Shape Pool coverage."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.placement_assignment import (
    AssignmentEngine,
    ImportedElementSlotProvider,
    PlacementAssignmentState,
    ShapePoolEntry,
    ShapePrototypeRegistry,
)
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import ModifierScope, ModifierScopeMode
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def make_document(count: int = 24) -> PatternDocument:
    elements = [
        CircleElement("dot-%03d" % index, (index % 8) * 11.0, (index // 8) * 11.0, 7, 7)
        for index in range(count)
    ]
    return PatternDocument(Canvas(150, 150, unit="mm", mm_per_unit=1.0), Reference(""), elements)


def pool() -> list[ShapePoolEntry]:
    return [
        ShapePoolEntry("circle", 40, True),
        ShapePoolEntry("diamond", 25, True),
        ShapePoolEntry("star", 20, True),
        ShapePoolEntry("triangle", 15, True),
        ShapePoolEntry("square", 0, False),
        ShapePoolEntry("line", 0, False),
    ]


class ShapePoolCoreTests(unittest.TestCase):
    def test_stable_assignment_is_order_independent_and_seed_sensitive(self):
        document = make_document(100)
        slots = ImportedElementSlotProvider.from_elements(document.elements)
        engine = AssignmentEngine(ShapePrototypeRegistry.with_builtins())
        first = engine.evaluate(slots, document.elements, shape_pool=pool(), shape_pool_enabled=True, shape_random_seed=58321)
        second = engine.evaluate(list(reversed(slots)), document.elements, shape_pool=pool(), shape_pool_enabled=True, shape_random_seed=58321)
        by_id_first = {element.id: element.type for element in first}
        by_id_second = {element.id: element.type for element in second}
        self.assertEqual(by_id_first, by_id_second)
        third = engine.evaluate(slots, document.elements, shape_pool=pool(), shape_pool_enabled=True, shape_random_seed=58322)
        self.assertNotEqual(by_id_first, {element.id: element.type for element in third})

    def test_manual_replacement_wins_and_zero_weight_falls_back_to_original(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document())
            source_before = deepcopy(session.document.elements)
            session.update_shape_pool(pool(), enabled=True, seed=58321)
            session.select("dot-000")
            session.replace_selected_shape("star")
            state = PlacementAssignmentState.from_document(session.document)
            self.assertEqual(state.replacement_map.values["dot-000"], "star")
            self.assertEqual(session.document.element("dot-000").type, "filled_region")
            self.assertEqual(state.source_snapshot(), source_before)
            # Removing the manual mapping exposes the derived random result,
            # never destroys or rewrites the original Circle source.
            session.restore_selected_shape()
            state = PlacementAssignmentState.from_document(session.document)
            self.assertNotIn("dot-000", state.replacement_map.values)
            self.assertEqual(state.source_snapshot(), source_before)

            zero = [ShapePoolEntry(entry.prototype_id, 0, True) for entry in pool()]
            session.update_shape_pool(zero, enabled=True, seed=9)
            self.assertTrue(all(element.type == "circle" for element in session.document.elements))

    def test_save_load_undo_redo_seed_and_svg_are_durable(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document(48))
            source_before = deepcopy(session.document.elements)
            session.update_shape_pool(pool(), enabled=True, seed=58321)
            assigned = [(element.id, element.type) for element in session.document.elements]
            before = session.undo_record_count
            session.set_shape_random_seed(91827)
            changed = [(element.id, element.type) for element in session.document.elements]
            self.assertNotEqual(assigned, changed)
            self.assertEqual(session.undo_record_count, before + 1)
            session.undo()
            self.assertEqual([(element.id, element.type) for element in session.document.elements], assigned)
            session.redo()
            self.assertEqual([(element.id, element.type) for element in session.document.elements], changed)
            saved = session.save_document(root / "shape-pool.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual([(element.id, element.type) for element in restored.document.elements], changed)
            state = PlacementAssignmentState.from_document(restored.document)
            self.assertTrue(state.shape_pool_enabled)
            self.assertEqual(state.shape_random_seed, 91827)
            self.assertEqual(state.source_snapshot(), source_before)
            svg = restored.export_svg(str(root / "shape-pool.svg"))
            text = svg.read_text(encoding="utf-8")
            self.assertIn("<path", text)
            self.assertNotIn("random_settings", text)

    def test_change_variant_is_one_undo_and_manual_replacement_survives(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document(48))
            session.update_shape_pool(pool(), enabled=True, seed=58321)
            session.select_many(["dot-000", "dot-001"])
            session.replace_selected_shape("star")
            before_seed = session.shape_pool_state().shape_random_seed
            before_undo = session.undo_record_count
            new_seed = session.randomize_shape_seed()
            self.assertNotEqual(before_seed, new_seed)
            self.assertEqual(session.undo_record_count, before_undo + 1)
            self.assertTrue(all(session.document.element(identifier).type == "filled_region" for identifier in session.selected_ids))
            session.undo()
            self.assertEqual(session.shape_pool_state().shape_random_seed, before_seed)
            self.assertTrue(all(session.document.element(identifier).type == "filled_region" for identifier in session.selected_ids))

    def test_old_document_remains_a_noop_and_assignment_is_lightweight(self):
        legacy = make_document(6)
        self.assertEqual(evaluate_pattern_document(legacy), legacy.elements)
        engine = AssignmentEngine(ShapePrototypeRegistry.with_builtins())
        for count in (100, 500, 1000, 3000):
            document = make_document(count)
            slots = ImportedElementSlotProvider.from_elements(document.elements)
            started = perf_counter()
            result = engine.evaluate(slots, document.elements, shape_pool=pool(), shape_pool_enabled=True, shape_random_seed=42)
            self.assertEqual(len(result), count)
            self.assertLess(perf_counter() - started, 3.0, "%d slots" % count)

    def test_scope_limits_seeded_pool_but_manual_replacement_still_wins(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document(12))
            star_only = [ShapePoolEntry("star", 100.0, True)]
            selected_scope = ModifierScope(
                mode=ModifierScopeMode.SELECTED,
                selected_element_ids=["dot-001", "dot-004"],
            )
            session.update_shape_pool(star_only, enabled=True, seed=41, scope=selected_scope)
            self.assertEqual(session.document.element("dot-001").type, "filled_region")
            self.assertEqual(session.document.element("dot-004").type, "filled_region")
            self.assertEqual(session.document.element("dot-002").type, "circle")

            # A direct local edit is intentionally stronger than the pool
            # Scope; it remains editable outside the generated region.
            session.select("dot-002")
            session.replace_selected_shape("diamond")
            self.assertEqual(session.document.element("dot-002").type, "filled_region")
            before_scope_undo = session.undo_record_count
            session.set_shape_pool_scope(ModifierScope(
                mode=ModifierScopeMode.CIRCLE, center_x=11.0, center_y=0.0, radius=0.5,
            ))
            self.assertEqual(session.undo_record_count, before_scope_undo + 1)
            self.assertEqual(session.document.element("dot-001").type, "filled_region")
            self.assertEqual(session.document.element("dot-004").type, "circle")
            self.assertEqual(session.document.element("dot-002").type, "filled_region")

            session.undo()
            self.assertEqual(session.shape_pool_state().shape_pool_scope.mode, ModifierScopeMode.SELECTED)
            self.assertEqual(session.document.element("dot-004").type, "filled_region")
            session.redo()
            self.assertEqual(session.document.element("dot-004").type, "circle")
            svg = session.export_svg(root / "scoped-shape-pool.svg").read_text(encoding="utf-8")
            self.assertIn("<path", svg)
            self.assertIn("<circle", svg)

            saved = session.save_document(root / "scoped-shape-pool.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            scope = restored.shape_pool_state().shape_pool_scope
            self.assertEqual(scope.mode, ModifierScopeMode.CIRCLE)
            self.assertEqual(scope.radius, 0.5)
            self.assertEqual(restored.document.element("dot-002").type, "filled_region")


class ShapePoolUITests(unittest.TestCase):
    def test_chinese_pool_controls_commit_and_reset_without_mutating_sources(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                source_before = deepcopy(app.session.document.elements)
                app.shape_pool_enabled_var.set(True)
                app.shape_pool_enabled_vars["circle"].set(True)
                app.shape_pool_weight_vars["circle"].set("0")
                app.shape_pool_enabled_vars["star"].set(True)
                app.shape_pool_weight_vars["star"].set("100")
                app.shape_random_seed_var.set("58321")
                app._commit_shape_pool_controls(); app.update()
                state = app.session.shape_pool_state()
                self.assertTrue(state.shape_pool_enabled)
                self.assertEqual(state.shape_random_seed, 58321)
                self.assertTrue(all(element.type == "filled_region" for element in app.session.document.elements))
                self.assertEqual(state.source_snapshot(), source_before)
                selected_ids = [element.id for element in app.session.document.elements[:2]]
                app.session.select_many(selected_ids)
                app.shape_pool_scope_mode_display_var.set("当前选择")
                app._on_shape_pool_scope_mode_selected(); app.update()
                state = app.session.shape_pool_state()
                self.assertEqual(state.shape_pool_scope.mode, ModifierScopeMode.SELECTED)
                self.assertEqual(set(state.shape_pool_scope.selected_element_ids), set(selected_ids))
                app._reset_shape_pool(); app.update()
                state = app.session.shape_pool_state()
                self.assertFalse(state.shape_pool_enabled)
                self.assertEqual(
                    [element.type for element in app.session.document.elements],
                    [element.type for element in source_before],
                )
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
