"""Gate S: real persistence/session transactions and isolated Tk file callbacks."""
from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from PIL import Image
from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from ppg.foundation.storage import atomic_write_json, load_pattern_document
from xiaomang_pattern_lab.project_workflow import ProjectFiles
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import CompositeField, ConstantField, FieldRegistry, SharedFieldEngine


def document():
    return PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1), Reference(""),
                           [CircleElement("a", 20, 20, 10, 10), CircleElement("b", 40, 20, 5, 5)])


class ProjectSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = PatternLabSession(FoundationPipeline(None, None), self.root / "work",
                                        document=document(), app_data_dir=self.root / "app-data")

    def save(self):
        return self.session.save_document(self.root / "design.pattern.json")

    def move(self):
        self.session.select("a")
        self.session.move_selected(2, 3)

    def test_new_project_clears_path_history_selection_not_presets(self):
        preset = self.session.save_parametric_preset("保留")
        self.save(); self.move()
        self.session.new_document()
        self.assertEqual(self.session.document.elements, [])
        self.assertEqual(self.session.current_project_name, "未命名")
        self.assertIsNone(self.session.current_project_path)
        self.assertTrue(self.session.is_dirty)
        self.assertEqual(self.session._undo_stack, [])
        self.assertEqual(self.session.selected_ids, [])
        self.assertTrue((self.session.workspace / "presets" / (preset.preset_id + ".preset.json")).exists())

    def test_open_success_and_save_as_checkpoint(self):
        first = self.save()
        self.move()
        second = self.session.save_document(self.root / "second.pattern.json")
        self.assertEqual(self.session.current_project_path, second)
        self.assertFalse(self.session.is_dirty)
        self.session.load_document(str(first))
        self.assertEqual(self.session.document.element("a").x, 20)
        self.assertEqual(self.session.current_project_path, first)
        self.assertFalse(self.session.is_dirty)

    def test_failed_open_preserves_document_path_dirty_and_undo(self):
        first = self.save(); self.move()
        before = self.session.document.to_dict()
        revision = self.session.revision
        payload = document().to_dict()
        payload["fields"] = [CompositeField("cycle", "cycle", "cycle").to_dict()]
        bad = atomic_write_json(self.root / "bad.json", payload)
        with self.assertRaises(ValueError):
            self.session.load_document(str(bad))
        self.assertEqual(self.session.document.to_dict(), before)
        self.assertEqual(self.session.revision, revision)
        self.assertEqual(self.session.current_project_path, first)
        self.assertTrue(self.session.is_dirty)
        self.assertTrue(self.session.undo())
        self.assertFalse(self.session.is_dirty)

    def test_dirty_undo_redo_checkpoint_and_branch(self):
        self.save(); self.move()
        self.assertTrue(self.session.is_dirty)
        self.session.undo(); self.assertFalse(self.session.is_dirty)
        self.session.redo(); self.assertTrue(self.session.is_dirty)
        self.session.save_document(); self.assertFalse(self.session.is_dirty)
        self.session.undo(); self.assertTrue(self.session.is_dirty)
        self.session.redo(); self.assertFalse(self.session.is_dirty)
        self.session.undo(); self.move()
        self.assertTrue(self.session.is_dirty)  # same stack length is not a checkpoint

    def test_selection_and_dirty_reads_do_not_serialize(self):
        self.save()
        with patch.object(PatternDocument, "to_dict", side_effect=AssertionError("serialized dirty check")):
            self.session.select("a")
            self.assertFalse(self.session.is_dirty)
            self.assertEqual(self.session.current_project_name, "design")

    def test_atomic_save_failure_preserves_official_bytes_and_dirty(self):
        target = self.save(); before = target.read_bytes(); self.move()
        with patch("ppg.foundation.storage.os.replace", side_effect=OSError("disk blocked")):
            with self.assertRaises(OSError):
                self.session.save_document()
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(self.session.is_dirty)
        self.assertEqual(list(self.root.glob(".pattern-*.tmp")), [])

    def test_recent_projects_dedup_limit_persist(self):
        store = self.session.project_files
        for number in range(12):
            store.remember(self.root / (str(number) + ".json"))
        store.remember(self.root / "5.json")
        restarted = ProjectFiles(self.session.workspace, self.root / "app-data")
        self.assertEqual(len(restarted.recent()), 10)
        self.assertEqual(Path(restarted.recent()[0]).name, "5.json")
        restarted.forget(self.root / "5.json")
        self.assertEqual(len(restarted.recent()), 9)

    def test_recovery_separate_from_official_and_skips_active_gesture(self):
        target = self.save(); before = target.read_bytes(); self.move()
        self.session.begin_transaction("gesture")
        self.assertIsNone(self.session.autosave_recovery())
        self.session.cancel_transaction()
        recovery = self.session.autosave_recovery()
        self.assertNotEqual(recovery, target)
        self.assertEqual(target.read_bytes(), before)
        self.assertIsNone(self.session.autosave_recovery())
        self.assertIn("app-data", str(recovery))

    def test_recovery_restore_dirty_preserves_formal_path_and_cleans_after_save(self):
        target = self.save(); self.move()
        recovery = self.session.autosave_recovery()
        payload = json.loads(recovery.read_text(encoding="utf-8")); payload["owner_pid"] = 0
        atomic_write_json(recovery, payload)
        restored = PatternLabSession(FoundationPipeline(None, None), self.session.workspace,
                                     app_data_dir=self.root / "app-data")
        self.assertEqual(restored.project_files.recoveries(), [recovery])
        restored.restore_recovery(recovery)
        self.assertTrue(restored.is_dirty)
        self.assertEqual(restored.current_project_path, target)
        self.assertEqual(restored.document.element("a").x, 22)
        self.assertEqual(load_pattern_document(str(target)).element("a").x, 20)
        restored.save_document()
        self.assertFalse(restored.project_files.recovery_path.exists())
        self.assertFalse(recovery.exists())

    def test_active_instance_recovery_not_offered(self):
        self.session.autosave_recovery()
        other = ProjectFiles(self.session.workspace, self.root / "app-data")
        self.assertEqual(other.recoveries(), [])

    def test_real_abnormal_process_exit_recovery(self):
        script = (
            "import os,sys; from pathlib import Path; "
            "from ppg.foundation import FoundationPipeline; "
            "from xiaomang_pattern_lab.session import PatternLabSession; "
            "s=PatternLabSession(FoundationPipeline(None,None),Path(sys.argv[1]),app_data_dir=Path(sys.argv[2])); "
            "s.new_document(); s.autosave_recovery(); os._exit(7)"
        )
        result = subprocess.run([sys.executable, "-c", script, str(self.session.workspace),
                                 str(self.root / "app-data")], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 7, result.stderr)
        copies = self.session.project_files.recoveries()
        self.assertEqual(len(copies), 1)
        self.session.restore_recovery(copies[0])
        self.assertTrue(self.session.is_dirty)
        self.assertEqual(self.session.document.elements, [])

    def test_invalid_json_open_and_invalid_recovery_are_non_destructive(self):
        path = self.root / "directory.json"; path.mkdir()
        before = self.session.document.to_dict()
        with self.assertRaises(OSError):
            self.session.load_document(str(path))
        self.assertEqual(self.session.document.to_dict(), before)
        atomic_write_json(self.session.project_files.recovery_dir / "bad.recovery.json", {"recovery_version": 99})
        self.assertEqual(self.session.project_files.recoveries(), [])

    def test_legacy_schema_defaults_and_future_version_rejected(self):
        payload = document().to_dict()
        for key in ("schema_version", "fields", "modifiers", "reference"):
            payload.pop(key)
        path = atomic_write_json(self.root / "old.json", payload)
        self.session.load_document(str(path))
        self.assertEqual(self.session.document.fields, [])
        payload["schema_version"] = 999
        atomic_write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "版本"):
            self.session.load_document(str(path))

    def test_missing_reference_keeps_geometry_and_relink_undo(self):
        self.session.document.reference.source_path = str(self.root / "lost.png")
        self.save(); self.session.load_document(str(self.session.current_project_path))
        self.assertTrue(self.session.missing_reference)
        self.assertEqual(len(self.session.document.elements), 2)
        self.assertEqual(self.session.document.element("a").width, 10)
        image = self.root / "found.png"; Image.new("L", (10, 10), 255).save(image)
        before = deepcopy(self.session.document.elements)
        self.session.relink_reference(str(image))
        self.assertFalse(self.session.missing_reference)
        self.assertEqual(self.session.document.elements, before)
        self.assertTrue(self.session.is_dirty)
        self.session.undo(); self.assertTrue(self.session.missing_reference)
        self.assertFalse(self.session.is_dirty)

    def test_gate_r_graph_roundtrip_svg_and_preset_isolation(self):
        engine = SharedFieldEngine(FieldRegistry([ConstantField("a", .5), ConstantField("b", .2),
                                    CompositeField("c", "a", "b", "multiply")]), [])
        self.session.document.fields = engine.to_dict()["fields"]
        preset = self.session.save_parametric_preset("组合")
        preset_path = self.session.workspace / "presets" / (preset.preset_id + ".preset.json")
        preset_bytes = preset_path.read_bytes()
        expected = self.session.document.to_dict()
        before_svg = self.session.export_svg().read_bytes()
        target = self.save(); self.session.load_document(str(target))
        self.assertEqual(self.session.document.to_dict(), expected)
        self.assertEqual(self.session.export_svg().read_bytes(), before_svg)
        self.assertEqual(preset_path.read_bytes(), preset_bytes)
        self.assertNotIn(str(preset_path), self.session.project_files.recent())
        with self.assertRaises(ValueError):
            self.session.load_document(str(preset_path))


class ProjectWorkflowTkTests(unittest.TestCase):
    def setUp(self):
        from xiaomang_pattern_lab.ui_harness import PatternLabApp
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = PatternLabApp(str(self.root / "work"), app_data_dir=self.root / "app")
        self.addCleanup(self.app.destroy)
        self.app.session.document = document()
        self.app._after_document_change()
        self.app.update()

    def test_unsaved_cancel_blocks_new_open_and_close(self):
        target = atomic_write_json(self.root / "other.json", document().to_dict())
        before = self.app.session.document
        with patch.object(self.app, "_ask_unsaved_changes", return_value="cancel"):
            self.assertFalse(self.app.new_project())
            self.assertFalse(self.app.open_project_path(target))
            self.assertFalse(self.app.request_close())
        self.assertIs(self.app.session.document, before)
        self.assertTrue(self.app.winfo_exists())

    def test_unsaved_save_and_new_with_real_disk(self):
        target = self.root / "saved.json"
        with patch.object(self.app, "_ask_unsaved_changes", return_value="save"), \
             patch("xiaomang_pattern_lab.project_ui.filedialog.asksaveasfilename", return_value=str(target)):
            self.assertTrue(self.app.new_project())
        self.assertEqual(len(load_pattern_document(str(target)).elements), 2)
        self.assertEqual(len(self.app.session.document.elements), 0)
        self.assertIn("未命名 *", self.app.title())

    def test_save_failure_or_cancel_prevents_closing(self):
        with patch.object(self.app, "_ask_unsaved_changes", return_value="save"), \
             patch("xiaomang_pattern_lab.project_ui.filedialog.asksaveasfilename", return_value=""):
            self.assertFalse(self.app.request_close())
        with patch.object(self.app, "_ask_unsaved_changes", return_value="save"), \
             patch("xiaomang_pattern_lab.project_ui.filedialog.asksaveasfilename", return_value=str(self.root / "save.json")), \
             patch.object(self.app.session, "save_document", side_effect=OSError("denied")), \
             patch("xiaomang_pattern_lab.project_ui.messagebox.showerror"):
            self.assertFalse(self.app.request_close())
        self.assertTrue(self.app.session.is_dirty)

    def test_save_reuses_path_save_as_updates_and_shortcuts_exist(self):
        one, two = self.root / "one.json", self.root / "two.json"
        with patch("xiaomang_pattern_lab.project_ui.filedialog.asksaveasfilename", return_value=str(one)) as choose:
            self.assertTrue(self.app.save_document())
            self.assertTrue(self.app.save_document())
            self.assertEqual(choose.call_count, 1)
        with patch("xiaomang_pattern_lab.project_ui.filedialog.asksaveasfilename", return_value=str(two)):
            self.assertTrue(self.app.save_document_as())
        self.assertEqual(self.app.session.current_project_path, two)
        self.assertNotIn("*", self.app.title())
        for key in ("<Control-n>", "<Control-o>", "<Control-s>", "<Control-Shift-S>"):
            self.assertTrue(self.app.bind(key))

    def test_missing_recent_does_not_touch_current_document(self):
        missing = self.root / "missing.json"
        self.app.session.project_files.remember(missing)
        before = self.app.session.document
        with patch("xiaomang_pattern_lab.project_ui.messagebox.showwarning"):
            self.assertFalse(self.app.open_project_path(missing))
        self.assertEqual(self.app.session.project_files.recent(), [])
        self.assertIs(self.app.session.document, before)

    def test_autosave_is_debounced_and_not_written_during_preview(self):
        self.app.AUTOSAVE_DELAY_MS = 30
        with patch.object(self.app.session, "autosave_recovery", wraps=self.app.session.autosave_recovery) as save:
            for _ in range(10): self.app._on_project_state_changed()
            self.assertEqual(save.call_count, 0)
            self.app._pending_project_preview = "grid"
            time.sleep(.04); self.app.update()
            self.assertEqual(save.call_count, 0)
            self.app._pending_project_preview = None
            time.sleep(.04); self.app.update()
            self.assertEqual(save.call_count, 1)
        self.assertTrue(self.app.session.project_files.recovery_path.exists())

    def test_normal_exit_discards_recovery_and_missing_reference_view_is_vector(self):
        self.app.session.document.reference.source_path = str(self.root / "missing.png")
        self.app._reset_project_view(); self.app.update()
        self.assertEqual(self.app.mode.get(), "vector")
        self.assertTrue(self.app.canvas.find_withtag("static"))
        self.app.session.autosave_recovery()
        path = self.app.session.project_files.recovery_path
        with patch.object(self.app, "_ask_unsaved_changes", return_value="discard"):
            self.assertTrue(self.app.request_close())
        self.assertFalse(path.exists())

    def test_title_checkpoint_undo_redo(self):
        self.app.session.save_document(self.root / "title.json")
        self.app.session.select("a"); self.app.session.move_selected(1, 0)
        self.assertTrue(self.app.title().endswith(" *"))
        self.app.undo(); self.assertFalse(self.app.title().endswith(" *"))
        self.app.redo(); self.assertTrue(self.app.title().endswith(" *"))

    def test_save_commits_pending_grid_preview_once(self):
        from xiaomang_pattern_lab.parametric import GridParametricModel
        self.app.session.activate_grid(GridParametricModel(rows=2, columns=2))
        self.app._after_document_change()
        target = self.app.session.save_document(self.root / "grid.json")
        before = len(self.app.session._undo_stack)
        self.app.grid_vars["rows"].set("3")
        self.app._schedule_grid_preview()
        self.app.after_cancel(self.app._parameter_after)
        self.app._run_grid_preview()
        self.assertEqual(len(self.app.session.document.elements), 4)
        self.assertTrue(self.app.save_document())
        self.assertEqual(len(load_pattern_document(str(target)).elements), 6)
        self.assertEqual(len(self.app.session._undo_stack), before + 1)
        self.assertFalse(self.app.session.is_dirty)

    def test_free_parametric_field_undo_restores_saved_model_not_only_elements(self):
        self.app.session.activate_free_parametric()
        self.app._after_document_change()
        self.app.session.save_document(self.root / "free.json")
        before = self.app.session.document.to_dict()
        self.app.family_min_scale_var.set("0.3")
        self.app.family_max_scale_var.set("1.8")
        self.app.apply_family_fields()
        self.assertTrue(self.app.session.is_dirty)
        self.app.undo()
        self.assertFalse(self.app.session.is_dirty)
        self.assertEqual(self.app.session.document.to_dict(), before)

    def test_invalid_pending_preview_blocks_save_and_new(self):
        from xiaomang_pattern_lab.parametric import GridParametricModel
        self.app.session.activate_grid(GridParametricModel(rows=2, columns=2))
        self.app._after_document_change()
        target = self.app.session.save_document(self.root / "grid.json")
        before = target.read_bytes()
        self.app._schedule_grid_preview()
        with patch("xiaomang_pattern_lab.project_ui.messagebox.showerror"), \
             patch.object(self.app, "_grid_from_controls", side_effect=ValueError("行数必须是整数")):
            self.assertFalse(self.app.save_document())
            self.assertFalse(self.app.new_project())
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(len(self.app.session.document.elements), 4)

    def test_startup_recovery_callback_and_discard(self):
        from types import SimpleNamespace
        files = self.app.session.project_files
        old = ProjectFiles(self.app.session.workspace, self.root / "app")
        recovery = old.write_recovery(document(), None, 4)
        raw = json.loads(recovery.read_text(encoding="utf-8")); raw["owner_pid"] = 0
        atomic_write_json(recovery, raw)
        with patch("xiaomang_pattern_lab.project_ui.ProjectChoiceDialog", return_value=SimpleNamespace(result="recover")):
            self.app.check_project_recovery()
        self.assertTrue(self.app.session.is_dirty)
        self.assertEqual(len(self.app._static_element_items), 2)
        self.assertFalse(recovery.exists())
        another = old.write_recovery(document(), None, 5)
        raw["revision"] = 5; atomic_write_json(another, raw)
        with patch("xiaomang_pattern_lab.project_ui.ProjectChoiceDialog", return_value=SimpleNamespace(result="discard")):
            self.app.check_project_recovery()
        self.assertFalse(another.exists())


if __name__ == "__main__":
    unittest.main()
