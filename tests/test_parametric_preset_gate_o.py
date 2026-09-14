"""Gate O regression: local, portable parametric-effect presets."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.placement_assignment import RandomSettings, ShapePoolEntry
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import ModifierScope, ModifierScopeMode, PositionModifier
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def make_document(*, scale: float = 1.0, count: int = 12) -> PatternDocument:
    elements = [
        CircleElement("dot-%03d" % index, (index % 4) * 10.0 * scale,
                      (index // 4) * 10.0 * scale, 5.0 * scale, 5.0 * scale)
        for index in range(count)
    ]
    return PatternDocument(Canvas(1000 * scale, 1000 * scale, unit="mm", mm_per_unit=1.0), Reference(""), elements)


def signature(document: PatternDocument):
    return [(item.id, item.type, round(item.x, 8), round(item.y, 8), round(item.width, 8),
             round(item.height, 8), round(item.rotation, 8), item.visible)
            for item in document.elements]


class ParametricPresetTests(unittest.TestCase):
    def _configured_session(self, root: Path) -> PatternLabSession:
        session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
        session.add_modifier_layer("position", PositionModifier(mode="offset", offset_x=8.0, offset_y=-4.0).to_dict())
        session.update_shape_pool([ShapePoolEntry("circle", 50.0, True), ShapePoolEntry("star", 50.0, True)], enabled=True, seed=919)
        session.update_random_transforms(RandomSettings(
            enabled=True, seed=618, size_random=0.2, rotation_random=15.0,
            position_jitter_x=2.0, position_jitter_y=3.0, occupancy=0.75,
            scope=ModifierScope(mode=ModifierScopeMode.CIRCLE, center_x=15, center_y=10, radius=30),
        ))
        return session

    def test_save_apply_undo_and_source_integrity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._configured_session(root / "source")
            preset = source.save_parametric_preset("波浪织物 01")
            payload = preset.to_dict()
            encoded = (source.workspace / "presets" / (preset.preset_id + ".preset.json")).read_text(encoding="utf-8")
            self.assertNotIn("source_elements", encoded)
            self.assertNotIn("replacement_map", encoded)
            self.assertNotIn("selected_element_ids\": [\"dot", encoded)
            self.assertEqual(payload["schema_version"], 1)

            # Presets are intentionally local to each workspace.  Copying the
            # file is not necessary here: source and target share the same
            # ordinary local Pattern Lab workspace, as they do in the app.
            target = PatternLabSession(FoundationPipeline(None, None), source.workspace, document=make_document())
            before_source = deepcopy(target.document.elements)
            before = target.document.to_dict()
            undo_count = target.undo_record_count
            target.apply_parametric_preset(preset.preset_id)
            self.assertEqual(target.undo_record_count, undo_count + 1)
            self.assertNotEqual(signature(target.document), signature(PatternDocument.from_dict(before)))
            self.assertEqual(target.shape_pool_state().source_snapshot(), before_source)
            self.assertEqual(target.random_transform_state().seed, 618)
            self.assertEqual(target.shape_pool_state().shape_random_seed, 919)
            self.assertTrue(target.undo())
            self.assertEqual(target.document.to_dict(), before)
            self.assertTrue(target.redo())
            self.assertEqual(target.shape_pool_state().source_snapshot(), before_source)
            svg = target.export_svg(source.workspace / "preset-final.svg").read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            self.assertNotIn("random_settings", svg)

    def test_repository_lifecycle_restart_and_project_roundtrip(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = self._configured_session(root)
            saved = session.save_parametric_preset("测试预设")
            self.assertEqual([item.name for item in session.list_parametric_presets()], ["测试预设"])
            copied = session.duplicate_parametric_preset(saved.preset_id, "测试预设 副本")
            renamed = session.rename_parametric_preset(copied.preset_id, "重命名预设")
            self.assertEqual(renamed.name, "重命名预设")
            restarted = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            self.assertEqual([item.name for item in restarted.list_parametric_presets()], ["测试预设", "重命名预设"])
            restarted.delete_parametric_preset(saved.preset_id)
            self.assertEqual([item.name for item in restarted.list_parametric_presets()], ["重命名预设"])

            target = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            target.apply_parametric_preset(renamed.preset_id)
            project = target.save_document(root / "preset-project.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "other-session")
            restored.load_document(str(project))
            self.assertEqual(signature(restored.document), signature(target.document))
            self.assertEqual(restored.random_transform_state().to_dict(), target.random_transform_state().to_dict())

    def test_bounds_adaptation_preserves_normalized_effect_scale(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = PatternLabSession(FoundationPipeline(None, None), root, document=make_document(scale=1.0))
            source.add_modifier_layer("position", PositionModifier(mode="offset", offset_x=8.0, offset_y=-4.0).to_dict())
            preset = source.save_parametric_preset("缩放适配")
            target = PatternLabSession(FoundationPipeline(None, None), root, document=make_document(scale=2.0))
            target.apply_parametric_preset(preset.preset_id)
            # Source document's 30 mm wide bounds maps to 60 mm in target;
            # an 8/-4 mm displacement therefore maps to 16/-8 mm.
            target_first = target.document.element("dot-000")
            self.assertAlmostEqual(target_first.x, 16.0, places=6)
            self.assertAlmostEqual(target_first.y, -8.0, places=6)

    def test_future_unknown_modifier_is_skipped_safely(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=make_document())
            preset = session.save_parametric_preset("未知层")
            raw = preset.to_dict()
            raw["shared_modifier_stack"] = {"enabled": True, "modifiers": [
                {"id": "future", "type": "future_magic", "enabled": True, "parameters": {}},
            ]}
            (root / "presets" / (preset.preset_id + ".preset.json")).write_text(__import__("json").dumps(raw), encoding="utf-8")
            session.apply_parametric_preset(preset.preset_id)
            self.assertTrue(any("跳过" in entry.message for entry in session.logs))
            self.assertEqual(len(session.document.elements), 12)

    def test_selected_scope_never_captures_source_document_selection_ids(self):
        with TemporaryDirectory() as directory:
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=make_document())
            selected = ModifierScope(mode=ModifierScopeMode.SELECTED, selected_element_ids=["dot-000", "dot-001"])
            session.update_shape_pool([ShapePoolEntry("star", 100.0, True)], enabled=True, seed=3, scope=selected)
            session.update_random_transforms(RandomSettings(enabled=True, seed=9, size_random=0.2, scope=selected))
            preset = session.save_parametric_preset("选择范围")
            payload = preset.to_dict()
            self.assertEqual(payload["shape_pool"]["shape_pool_scope"]["selected_element_ids"], [])
            self.assertEqual(payload["random_settings"]["scope"]["selected_element_ids"], [])


class ParametricPresetUITests(unittest.TestCase):
    def test_chinese_preset_panel_saves_and_applies_without_project_snapshot(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app._import(str(app._fixtures["regular_dot_matrix"]))
                first_id = app.session.document.elements[0].id
                first_x = app.session.document.elements[0].x
                app.session.add_modifier_layer(
                    "position", PositionModifier(mode="offset", offset_x=4.0).to_dict(),
                )
                app._save_preset_with_name("UI 预设")
                self.assertIsNotNone(app._preset_listbox)
                self.assertEqual(app._preset_listbox.size(), 1)
                preset_id = app._preset_ids[0]
                app.session.deactivate_shared_modifiers()
                self.assertAlmostEqual(app.session.document.element(first_id).x, first_x)
                app.session.apply_parametric_preset(preset_id)
                self.assertAlmostEqual(app.session.require_document().element(first_id).x, first_x + 4.0)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
