"""F1: fabric bases remain derived, validated, and compatible with legacy builds."""
from __future__ import annotations

from copy import deepcopy
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
import trimesh

from ppg.foundation import Canvas, FoundationPipeline, PatternDocument, RectElement, Reference
from ppg.foundation import load_pattern_document, save_pattern_document
from tests.test_manufacturing_service_wm1 import printed_pattern_document
from tests.test_web_server_wm3 import build_payload
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_base import BaseDefinition, FabricBaseBuilder, FabricConfig
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app


def rectangle() -> PatternDocument:
    return PatternDocument(Canvas(80, 70, "mm", 1), Reference("", False),
                           [RectElement("area", 25, 20, 50, 40)])


def configured(document: PatternDocument, kind: str, **parameters) -> PatternDocument:
    document.metadata["fabric_config"] = {"config_version": 1,
        "base": {"type": kind, "thickness_mm": 0.6, "margin_mm": 0, **parameters}}
    return document


class FabricBaseF1Tests(unittest.TestCase):
    def test_solid_and_grid_bounds_watertight_and_connected(self):
        for kind, parameters in (("solid", {}), ("grid", {
            "spacing_x_mm": 5, "spacing_y_mm": 5, "line_width_mm": 1,
        })):
            with self.subTest(kind=kind), TemporaryDirectory() as temporary:
                doc = configured(rectangle(), kind, **parameters)
                snapshot = deepcopy(doc.to_dict())
                session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=doc)
                result = ManufacturingService().build(session, 0.6)
                self.assertTrue(result.ready)
                self.assertEqual(result.mesh_result.size, (50.0, 40.0, 0.6))
                self.assertEqual(result.mesh_result.bounds[0][2], 0.0)
                self.assertEqual(result.component_count, 1)
                self.assertTrue(result.mesh_report.is_watertight)
                self.assertEqual(result.mesh_report.error_count, 0)
                self.assertEqual(doc.to_dict(), snapshot)
                exported = STLExporter().export_bytes(result.mesh_result)
                reloaded = trimesh.load(io.BytesIO(exported), file_type="stl", force="mesh")
                self.assertTrue(reloaded.is_watertight)
                self.assertAlmostEqual(reloaded.extents[2], 0.6, places=5)

    def test_config_round_trip_and_legacy_path_unchanged(self):
        with TemporaryDirectory() as temporary:
            doc = configured(rectangle(), "grid", spacing_x_mm=5, spacing_y_mm=5, line_width_mm=1)
            target = save_pattern_document(doc, str(Path(temporary) / "fabric.pattern.json"))
            loaded = load_pattern_document(str(target))
            self.assertEqual(loaded.to_dict(), doc.to_dict())
            default = rectangle()
            self.assertNotIn("fabric_config", default.to_dict()["metadata"])
            result = ManufacturingService().build(PatternLabSession(
                FoundationPipeline(None, None), Path(temporary), document=default), 2)
            self.assertEqual(result.mesh_result.backend_name, "trimesh-earcut")
            self.assertEqual(result.mesh_result.size, (50.0, 40.0, 2.0))

    def test_margin_expands_final_design_bounds_in_mm(self):
        base = BaseDefinition.from_mapping({"type": "solid", "thickness_mm": .6, "margin_mm": 2})
        mesh = FabricBaseBuilder().build((0, 0, 50, 40), base)
        self.assertEqual(mesh.bounds, ((-2, -2, 0), (52, 42, .6)))
        self.assertTrue(MeshValidator().validate(mesh).is_valid)

    def test_invalid_config_and_thickness_are_rejected(self):
        invalid = [
            {"type": "solid", "thickness_mm": 0, "margin_mm": 0},
            {"type": "solid", "thickness_mm": float("nan"), "margin_mm": 0},
            {"type": "grid", "thickness_mm": .6, "margin_mm": 0,
             "spacing_x_mm": 0, "spacing_y_mm": 5, "line_width_mm": 1},
            {"type": "grid", "thickness_mm": .6, "margin_mm": 0,
             "spacing_x_mm": 5, "spacing_y_mm": 5, "line_width_mm": 0},
            {"type": "grid", "thickness_mm": .6, "margin_mm": 0,
             "spacing_x_mm": 5, "spacing_y_mm": 5, "line_width_mm": 6},
        ]
        for base in invalid:
            with self.subTest(base=base):
                with self.assertRaises(ValueError):
                    FabricConfig.from_mapping({"config_version": 1, "base": base})
        with TemporaryDirectory() as temporary:
            doc = configured(rectangle(), "solid")
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=doc)
            with self.assertRaisesRegex(ValueError, "厚度"):
                ManufacturingService().build(session, 2)

    def test_parameter_schema_and_web_artifacts_share_one_result(self):
        definitions = parameter_definitions()["definitions"]["fabric_base"]
        self.assertEqual({"solid", "grid"}, set(definitions))
        self.assertEqual({"thickness_mm", "margin_mm"},
                         {item["id"] for item in definitions["solid"]["parameters"]})
        self.assertEqual(5, len(definitions["grid"]["parameters"]))
        thickness = next(item for item in definitions["grid"]["parameters"] if item["id"] == "thickness_mm")
        self.assertEqual((thickness["slider_min"], thickness["slider_max"]), (0.1, 3))
        dto = PatternDocumentDTO.from_document(configured(rectangle(), "grid",
            spacing_x_mm=5, spacing_y_mm=5, line_width_mm=1), "fabric-grid", 4)
        with TestClient(create_app()) as client:
            built = client.post("/api/v1/manufacturing/build", json=build_payload(dto, .6))
            self.assertEqual(200, built.status_code, built.text)
            result_id = built.json()["manufacturing_result_id"]
            self.assertEqual(1, built.json()["component_count"])
            stl = client.get(f"/api/v1/manufacturing/{result_id}/model.stl")
            glb = client.get(f"/api/v1/manufacturing/{result_id}/preview.glb")
            self.assertEqual((200, 200), (stl.status_code, glb.status_code))
            for data, kind in ((stl.content, "stl"), (glb.content, "glb")):
                mesh = trimesh.load(io.BytesIO(data), file_type=kind, force="mesh")
                self.assertTrue(mesh.is_watertight)
                self.assertEqual(tuple(round(value, 5) for value in mesh.extents), (50, 40, .6))
            mismatch = client.post("/api/v1/manufacturing/build", json=build_payload(dto, 2))
            self.assertEqual(422, mismatch.status_code)
            self.assertEqual("invalid_fabric_base", mismatch.json()["code"])

    def test_real_printed_pattern_can_build_fabric_base(self):
        doc, _ = printed_pattern_document()
        configured(doc, "solid", margin_mm=1)
        with TemporaryDirectory() as temporary:
            result = ManufacturingService().build(PatternLabSession(
                FoundationPipeline(None, None), Path(temporary), document=doc), .6)
        self.assertTrue(result.ready)
        self.assertTrue(result.mesh_report.is_watertight)
        self.assertEqual(result.component_count, 1)
        self.assertGreater(result.mesh_result.size[0], 50)
        self.assertGreater(result.mesh_result.size[1], 19)


if __name__ == "__main__":
    unittest.main()
