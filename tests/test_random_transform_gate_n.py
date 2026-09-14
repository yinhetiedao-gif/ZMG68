"""Gate N: deterministic random transform and occupancy coverage."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.placement_assignment import (
    AssignmentEngine,
    ImportedElementSlotProvider,
    RandomSettings,
    ShapePoolEntry,
    ShapePrototypeRegistry,
)
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import ModifierScope, ModifierScopeMode
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def make_document(count: int = 16) -> PatternDocument:
    elements = [
        CircleElement("dot-%03d" % index, (index % 8) * 10.0, (index // 8) * 10.0, 6.0, 6.0)
        for index in range(count)
    ]
    return PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1.0), Reference(""), elements)


def element_signature(elements):
    return [
        (item.id, item.type, round(item.x, 9), round(item.y, 9), round(item.width, 9),
         round(item.height, 9), round(item.rotation, 9), item.visible)
        for item in elements
    ]


class RandomTransformCoreTests(unittest.TestCase):
    def test_seeded_channels_are_stable_and_independent(self):
        document = make_document(48)
        slots = ImportedElementSlotProvider.from_elements(document.elements)
        engine = AssignmentEngine(ShapePrototypeRegistry.with_builtins())
        base = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=71))
        sized = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=71, size_random=0.3))
        rotated = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=71, rotation_random=45.0))
        shifted = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=71, position_jitter_x=4.0, position_jitter_y=7.0))
        self.assertEqual(element_signature(sized), element_signature(engine.evaluate(
            list(reversed(slots)), document.elements,
            random_settings=RandomSettings(enabled=True, seed=71, size_random=0.3),
        ))[::-1])
        self.assertTrue(any(item.width != original.width for item, original in zip(sized, base)))
        self.assertTrue(all(item.x == original.x and item.y == original.y and item.rotation == original.rotation
                            for item, original in zip(sized, base)))
        self.assertTrue(all(item.width == original.width and item.height == original.height
                            for item, original in zip(rotated, base)))
        self.assertTrue(all(item.rotation != original.rotation for item, original in zip(rotated, base)))
        self.assertTrue(all(item.width == original.width and item.rotation == original.rotation
                            for item, original in zip(shifted, base)))
        self.assertTrue(any(item.x != original.x or item.y != original.y for item, original in zip(shifted, base)))
        changed_seed = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=72, size_random=0.3))
        self.assertNotEqual(element_signature(sized), element_signature(changed_seed))

    def test_scope_and_occupancy_are_derived_and_do_not_touch_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document(24))
            before_source = deepcopy(session.document.elements)
            scope = ModifierScope(mode=ModifierScopeMode.SELECTED, selected_element_ids=["dot-000", "dot-001"])
            settings = RandomSettings(enabled=True, seed=123, size_random=0.5, occupancy=0.0, scope=scope)
            session.update_random_transforms(settings)
            self.assertFalse(session.document.element("dot-000").visible)
            self.assertFalse(session.document.element("dot-001").visible)
            self.assertTrue(session.document.element("dot-002").visible)
            self.assertEqual(session.random_transform_state().scope.selected_element_ids, ["dot-000", "dot-001"])
            self.assertEqual(session.shape_pool_state().source_snapshot(), before_source)

            before_undo = session.undo_record_count
            half = RandomSettings(enabled=True, seed=123, occupancy=0.5, scope=ModifierScope())
            session.update_random_transforms(half)
            self.assertEqual(session.undo_record_count, before_undo + 1)
            first_visibility = [item.visible for item in session.document.elements]
            session.undo(); self.assertFalse(session.document.element("dot-000").visible)
            session.redo(); self.assertEqual([item.visible for item in session.document.elements], first_visibility)
            self.assertGreater(sum(first_visibility), 0)
            self.assertLess(sum(first_visibility), len(first_visibility))

            svg = session.export_svg(root / "random.svg").read_text(encoding="utf-8")
            self.assertEqual(svg.count("<circle"), sum(first_visibility))
            saved = session.save_document(root / "random.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual(element_signature(restored.document.elements), element_signature(session.document.elements))
            self.assertEqual(restored.random_transform_state().to_dict(), half.to_dict())

    def test_full_density_and_disabled_random_preserve_legacy_output(self):
        document = make_document(12)
        slots = ImportedElementSlotProvider.from_elements(document.elements)
        engine = AssignmentEngine(ShapePrototypeRegistry.with_builtins())
        disabled = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=False, seed=9, occupancy=0.0, size_random=1.0))
        full = engine.evaluate(slots, document.elements, random_settings=RandomSettings(enabled=True, seed=9, occupancy=1.0))
        self.assertEqual(element_signature(disabled), element_signature(document.elements))
        self.assertEqual(element_signature(full), element_signature(document.elements))

    def test_transform_seed_does_not_reshuffle_shape_pool(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document(40))
            pool = [ShapePoolEntry("circle", 50.0, True), ShapePoolEntry("star", 50.0, True)]
            session.update_shape_pool(pool, enabled=True, seed=991)
            assigned_before = [(item.id, item.type) for item in session.document.elements]
            session.update_random_transforms(RandomSettings(
                enabled=True, seed=11, size_random=0.2, rotation_random=20.0,
                position_jitter_x=1.0, position_jitter_y=1.0, occupancy=1.0,
            ))
            self.assertEqual(assigned_before, [(item.id, item.type) for item in session.document.elements])
            session.update_random_transforms(RandomSettings(
                enabled=True, seed=12, size_random=0.2, rotation_random=20.0,
                position_jitter_x=1.0, position_jitter_y=1.0, occupancy=1.0,
            ))
            self.assertEqual(assigned_before, [(item.id, item.type) for item in session.document.elements])


class RandomTransformUITests(unittest.TestCase):
    def test_chinese_random_panel_commits_scope_and_single_transaction(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                selected_ids = [item.id for item in app.session.document.elements[:2]]
                app.session.select_many(selected_ids)
                before = app.session.undo_record_count
                app.random_transform_enabled_var.set(True)
                app.random_transform_seed_var.set("7123")
                app.random_size_var.set("20")
                app.random_rotation_var.set("30")
                app.random_jitter_x_var.set("2")
                app.random_jitter_y_var.set("3")
                app.random_occupancy_var.set("50")
                app.random_scope_mode_display_var.set("当前选择")
                app._on_random_scope_mode_selected(); app.update()
                state = app.session.random_transform_state()
                self.assertTrue(state.enabled)
                self.assertEqual(state.seed, 7123)
                self.assertEqual(state.scope.mode, ModifierScopeMode.SELECTED)
                self.assertEqual(set(state.scope.selected_element_ids), set(selected_ids))
                self.assertGreaterEqual(app.session.undo_record_count, before + 1)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
