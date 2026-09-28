"""v0.2-M1: user manufacturing workflow delegates to the validated T→X pipeline."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ppg.foundation import Canvas, CircleElement, FilledRegionElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.manufacturing_ui import ManufacturingDialog, ManufacturingWorkflow, parse_height_mm
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.placement_assignment import ShapePrototypeRegistry
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import FieldMapping, FieldRegistry, SharedFieldEngine, SizeModifier, WaveField
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def document(elements) -> PatternDocument:
    return PatternDocument(Canvas(80, 50, "mm", 1.0), Reference("", False), list(elements))


def circles(count=1):
    return [CircleElement("dot-%d" % index, 15 + index * 25, 20, 12, 12) for index in range(count)]


class ManufacturingWorkflowTests(unittest.TestCase):
    def test_height_validation_rejects_non_positive_and_non_finite_values(self):
        for value in ("", "abc", "0", "-1", "nan", "inf", "-inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_height_mm(value)
        self.assertEqual(parse_height_mm("2.0"), 2.0)

    def test_prepare_and_export_are_read_only_and_gate_x_remains_authoritative(self):
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document(circles(2)))
            before = deepcopy(session.document.to_dict())
            state = (session.revision, session.saved_revision, session.undo_record_count, session.is_dirty)
            workflow = ManufacturingWorkflow()
            result = workflow.prepare(session, 2.0)
            self.assertTrue(result.ready)
            self.assertEqual(result.connectivity_report.component_count, 2)
            self.assertEqual(result.mesh_report.error_count, 0)
            self.assertTrue(result.mesh_report.is_watertight)
            target = Path(temporary) / "ui-export.stl"
            exported = workflow.export(session, result, target)
            reload_report = STLExporter().validator.validate(STLExporter().reload_as_mesh_result(target))
            self.assertEqual(exported.component_count, 2)
            self.assertEqual(result.build.mesh_result.size[2], 2.0)
            self.assertTrue(reload_report.is_valid)
            self.assertEqual(reload_report.component_count, 2)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.saved_revision, session.undo_record_count, session.is_dirty), state)

    def test_invalid_geometry_is_reported_without_build_or_export(self):
        invalid = FilledRegionElement(
            id="bow", x=0, y=0, width=10, height=10,
            path_data="M 0 0 L 10 10 L 0 10 L 10 0 Z",
            base_x=0, base_y=0, base_width=10, base_height=10,
            style={"fill": "#000", "stroke": "none"},
        )
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document([invalid]))
            result = ManufacturingWorkflow().prepare(session, 2.0)
            self.assertFalse(result.ready)
            self.assertGreater(result.geometry_report.error_count, 0)
            self.assertIsNone(result.build)
            with self.assertRaises(RuntimeError):
                ManufacturingWorkflow().export(session, result, Path(temporary) / "blocked.stl")

    def test_prepared_result_expires_after_design_or_height_changes(self):
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document(circles()))
            workflow = ManufacturingWorkflow(); result = workflow.prepare(session, 2.0)
            self.assertTrue(workflow.is_current(session, result, "2"))
            self.assertFalse(workflow.is_current(session, result, "3"))
            session.begin_transaction("edit")
            session.document.elements[0].x += 1
            session.commit_transaction()
            self.assertFalse(workflow.is_current(session, result, "2"))

    def test_gate_w_error_keeps_result_unexportable(self):
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document(circles()))
            original = session.validate_manufacturing_mesh
            session.validate_manufacturing_mesh = lambda mesh_result: replace(
                original(mesh_result), is_watertight=False, error_count=1,
            )
            result = ManufacturingWorkflow().prepare(session, 2.0)
            self.assertFalse(result.ready)
            self.assertEqual(result.mesh_report.error_count, 1)
            with self.assertRaises(RuntimeError):
                ManufacturingWorkflow().export(session, result, Path(temporary) / "blocked-w.stl")


class ManufacturingDialogTests(unittest.TestCase):
    def test_dialog_normal_multicomponent_export_and_invalid_height(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = PatternLabApp(str(root), app_data_dir=root / "appdata")
            try:
                app.withdraw()
                app.session.document = document(circles(3))
                dialog = ManufacturingDialog(app, app.session)
                dialog.withdraw(); dialog.update()
                self.assertIsInstance(dialog.service, ManufacturingService)
                dialog.height_var.set("0")
                self.assertIsNone(dialog.prepare())
                self.assertIn("无法生成", dialog.status_var.get())
                self.assertEqual(str(dialog.export_button.cget("state")), "disabled")
                dialog.height_var.set("2")
                result = dialog.prepare()
                self.assertIsNotNone(result); self.assertTrue(result.ready)
                self.assertIn("3 个独立组件", dialog.status_var.get())
                self.assertEqual(str(dialog.export_button.cget("state")), "normal")
                target = root / "dialog-real-pattern.stl"
                with patch("xiaomang_pattern_lab.manufacturing_ui.filedialog.asksaveasfilename", return_value=str(target)), \
                     patch("xiaomang_pattern_lab.manufacturing_ui.messagebox.showinfo") as success:
                    dialog.export_stl()
                self.assertTrue(target.is_file())
                success.assert_called_once()
                dialog.close()
            finally:
                app.destroy()

    def test_printed_pattern_type_exports_through_the_actual_ui_workflow(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = PatternLabApp(str(root), app_data_dir=root / "appdata")
            try:
                app.withdraw()
                model = GridParametricModel(
                    rows=1, columns=3, spacing_x=21, spacing_y=21,
                    element_width=16, element_height=16, offset_x=33, offset_y=15,
                    prototype=ShapePrototypeRegistry.with_builtins().get("star"),
                )
                app.session.document = document(model.generate())
                app.session.activate_grid(model)
                engine = SharedFieldEngine(
                    FieldRegistry([WaveField(
                        "print-wave", wavelength=84,
                        phase=-math.pi / 2 - 2 * math.pi * 12 / 84,
                    )]),
                    [SizeModifier(
                        "print-size", "print-wave",
                        FieldMapping(min_output=0.625, max_output=1.375),
                    )],
                )
                graph = engine.to_dict()
                app.session.document.fields, app.session.document.modifiers = graph["fields"], graph["modifiers"]
                before = deepcopy(app.session.document.to_dict())
                state = (app.session.revision, app.session.undo_record_count, app.session.is_dirty)
                app.open_manufacturing()
                dialog = app._manufacturing_dialog
                dialog.withdraw(); result = dialog.prepare()
                self.assertTrue(result.ready)
                self.assertEqual([round(item.width) for item in app.session.evaluate_elements()], [10, 16, 22])
                target = root / "physical-pattern-through-ui.stl"
                with patch("xiaomang_pattern_lab.manufacturing_ui.filedialog.asksaveasfilename", return_value=str(target)), \
                     patch("xiaomang_pattern_lab.manufacturing_ui.messagebox.showinfo"):
                    dialog.export_stl()
                reloaded = STLExporter().reload_as_mesh_result(target)
                report = STLExporter().validator.validate(reloaded)
                size = reloaded.size
                self.assertTrue(report.is_valid and report.is_watertight)
                self.assertEqual(report.component_count, 3)
                self.assertAlmostEqual(size[0], 57.2169065, places=4)
                self.assertAlmostEqual(size[1], 19.8991871, places=4)
                self.assertEqual(size[2], 2.0)
                self.assertEqual(app.session.document.to_dict(), before)
                self.assertEqual((app.session.revision, app.session.undo_record_count, app.session.is_dirty), state)
                dialog.close()
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
