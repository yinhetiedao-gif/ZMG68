"""WM1: the manufacturing application service is genuinely headless."""
from __future__ import annotations

from copy import deepcopy
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import (
    Canvas,
    CircleElement,
    FoundationPipeline,
    PatternDocument,
    Reference,
    load_pattern_document,
    save_pattern_document,
)
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.placement_assignment import ShapePrototypeRegistry
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import (
    FieldMapping,
    FieldRegistry,
    SharedFieldEngine,
    SizeModifier,
    WaveField,
)
from xiaomang_pattern_lab.stl_export import STLExporter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def document(elements) -> PatternDocument:
    return PatternDocument(Canvas(160, 120, "mm", 1.0), Reference("", False), list(elements))


def printed_pattern_document() -> tuple[PatternDocument, GridParametricModel]:
    model = GridParametricModel(
        rows=1,
        columns=3,
        spacing_x=21,
        spacing_y=21,
        element_width=16,
        element_height=16,
        offset_x=33,
        offset_y=15,
        prototype=ShapePrototypeRegistry.with_builtins().get("star"),
    )
    pattern = document(model.generate())
    engine = SharedFieldEngine(
        FieldRegistry([
            WaveField(
                "print-wave",
                wavelength=84,
                phase=-math.pi / 2 - 2 * math.pi * 12 / 84,
            ),
        ]),
        [
            SizeModifier(
                "print-size",
                "print-wave",
                FieldMapping(min_output=0.625, max_output=1.375),
            ),
        ],
    )
    graph = engine.to_dict()
    pattern.fields = graph["fields"]
    pattern.modifiers = graph["modifiers"]
    return pattern, model


class ManufacturingServiceImportBoundaryTests(unittest.TestCase):
    def test_fresh_import_does_not_load_tkinter_or_legacy_pipeline(self):
        command = (
            "import sys; import xiaomang_pattern_lab.manufacturing_service; "
            "assert 'tkinter' not in sys.modules; "
            "assert 'ppg.xiaomang_pipeline' not in sys.modules; "
            "print('HEADLESS_IMPORT_OK')"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(PROJECT_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", command],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("HEADLESS_IMPORT_OK", completed.stdout)


class ManufacturingServiceHeadlessTests(unittest.TestCase):
    def test_document_save_load_build_export_and_stl_reload_without_tk(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = document([CircleElement("dot", 20, 20, 12, 12)])
            project_path = save_pattern_document(source, str(root / "headless.pattern.json"))
            loaded = load_pattern_document(str(project_path))
            session = PatternLabSession(FoundationPipeline(None, None), root, document=loaded)
            result = ManufacturingService().build(session, 2.0)
            target = root / "headless.stl"
            exported = ManufacturingService().export_stl(session, result, target)
            reloaded = STLExporter().reload_as_mesh_result(target)
            report = STLExporter().validator.validate(reloaded)

            self.assertTrue(result.ready)
            self.assertTrue(result.mesh_report.is_watertight)
            self.assertEqual(result.manufacturing_bounds_mm, result.mesh_result.bounds)
            self.assertEqual(result.component_count, 1)
            self.assertEqual(exported.units_assumption, "mm")
            self.assertTrue(report.is_valid and report.is_watertight)
            self.assertEqual(report.component_count, 1)

    def test_real_printed_pattern_geometry_is_equivalent_and_read_only(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pattern, model = printed_pattern_document()
            session = PatternLabSession(FoundationPipeline(None, None), root, document=pattern)
            session.activate_grid(model)
            before = deepcopy(session.document.to_dict())
            state = (
                session.revision,
                session.saved_revision,
                session.undo_record_count,
                session.is_dirty,
            )
            service = ManufacturingService()
            result = service.build(session, height_mm=2.0)
            target = root / "physical-validation-02.stl"
            exported = service.export_stl(session, result, target)
            reloaded = STLExporter().reload_as_mesh_result(target)
            reload_report = STLExporter().validator.validate(reloaded)

            self.assertTrue(result.ready)
            self.assertEqual(result.component_count, 3)
            self.assertTrue(result.mesh_report.is_watertight)
            self.assertIn("Mesh 包含多个独立拓扑组件", " ".join(result.warnings))
            self.assertAlmostEqual(result.mesh_result.size[0], 57.2169065, places=4)
            self.assertAlmostEqual(result.mesh_result.size[1], 19.8991871, places=4)
            self.assertEqual(result.mesh_result.size[2], 2.0)
            self.assertEqual(exported.bounds, result.mesh_result.bounds)
            self.assertTrue(reload_report.is_valid and reload_report.is_watertight)
            self.assertEqual(reload_report.component_count, 3)
            self.assertAlmostEqual(reloaded.size[0], result.mesh_result.size[0], places=5)
            self.assertAlmostEqual(reloaded.size[1], result.mesh_result.size[1], places=5)
            self.assertAlmostEqual(reloaded.size[2], result.mesh_result.size[2], places=5)
            self.assertAlmostEqual(float(reloaded.mesh.volume), float(result.mesh_result.mesh.volume), places=4)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual(
                (session.revision, session.saved_revision, session.undo_record_count, session.is_dirty),
                state,
            )

    def test_build_is_current_contract_and_export_are_derived_operations(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = PatternLabSession(
                FoundationPipeline(None, None),
                root,
                document=document([CircleElement("dot", 20, 20, 12, 12)]),
            )
            service = ManufacturingService()
            result = service.build(session, 2)
            self.assertTrue(service.is_current(session, result, "2.0"))
            self.assertFalse(service.is_current(session, result, "3.0"))
            self.assertIs(result.mesh_result, result.build.mesh_result)
            self.assertEqual(result.manufacturing_bounds_mm, result.build.mesh_result.bounds)
            service.export_stl(session, result, root / "derived.stl")
            self.assertEqual(session.undo_record_count, 0)
            self.assertTrue(service.is_current(session, result, "2.0"))


if __name__ == "__main__":
    unittest.main()
