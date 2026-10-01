"""F2 preview-only unit-cell placement must not change the F1 manufacturing STL."""
from __future__ import annotations

import io
from pathlib import Path
import tempfile
from time import perf_counter
import unittest

from fastapi.testclient import TestClient
import trimesh

from tests.test_fabric_base_f1 import configured, rectangle
from tests.test_web_server_wm3 import build_payload
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_cells import CELL_TYPES, UNIT_CELL_REGISTRY, UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.web import create_app
from ppg.foundation import load_pattern_document, save_pattern_document


class FabricCellsF2Tests(unittest.TestCase):
    def test_five_prototypes_have_finite_bounds_and_base_at_zero(self):
        for kind in CELL_TYPES:
            with self.subTest(kind=kind):
                definition = UnitCellDefinition.from_mapping({"type": kind,
                    "width_mm": 2, "depth_mm": 3, "height_mm": 4})
                mesh = UNIT_CELL_REGISTRY.create(definition)
                self.assertEqual(tuple(mesh.extents), (2, 3, 4))
                self.assertEqual(mesh.bounds[0][2], 0)
                self.assertTrue(mesh.is_watertight)

    def test_50_by_40_regular_plan_count_and_z_contact(self):
        cell = UnitCellDefinition("pyramid", 2, 2, 3)
        plan = FabricPlanner().plan((0, 0, 50, 40), .6, cell, RegularPlacement(5, 5))
        self.assertEqual(plan.count, 80)
        self.assertEqual((plan.instances[0].x_mm, plan.instances[0].y_mm), (2.5, 2.5))
        self.assertEqual(plan.instances[-1].id, "fabric:r7:c9")
        self.assertTrue(all(instance.z_mm == .6 and instance.rotation_deg == 0
                            and instance.scale == 1 and instance.cell_type == "pyramid"
                            and instance.height_mm == 3 and instance.source_id is None
                            for instance in plan.instances))
        self.assertEqual(plan.bounds_mm[0][2], .6)
        self.assertEqual(plan.bounds_mm[1][2], 3.6)

    def test_20_by_20_instances_reuse_one_prototype(self):
        cell = UnitCellDefinition("fin", 1, 2, 2)
        start = perf_counter()
        plan = FabricPlanner().plan((0, 0, 100, 100), .6, cell, RegularPlacement(5, 5))
        elapsed = perf_counter() - start
        self.assertEqual(plan.count, 400)
        self.assertLess(len(plan.prototype.faces), 20)
        self.assertEqual(len(plan.preview_payload()["instances"]), 400)
        print(f"F2 400-instance plan: {elapsed * 1000:.2f} ms, one shared prototype")

    def test_invalid_dimensions_spacing_and_excess_count_rejected(self):
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                UnitCellDefinition.from_mapping({"type": "cone", "width_mm": invalid,
                    "depth_mm": 2, "height_mm": 3})
            with self.assertRaises(ValueError):
                UnitCellDefinition("cone", invalid, 2, 3)
        for invalid in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                RegularPlacement.from_mapping({"spacing_x_mm": invalid, "spacing_y_mm": 5})
            with self.assertRaises(ValueError):
                RegularPlacement(invalid, 5)
        with self.assertRaisesRegex(ValueError, "上限"):
            FabricPlanner().plan((0, 0, 200, 200), .6, UnitCellDefinition("cylinder", 1, 1, 2),
                                 RegularPlacement(1, 1))

    def test_python_schema_declares_all_cells_and_placement(self):
        definitions = parameter_definitions()["definitions"]
        self.assertEqual(set(CELL_TYPES), set(definitions["fabric_cell"]))
        self.assertEqual({"spacing_x_mm", "spacing_y_mm"},
                         {item["id"] for item in definitions["fabric_placement"]["regular"]["parameters"]})

    def test_unit_cell_config_survives_project_save_load(self):
        document = configured(rectangle(), "grid")
        document.metadata["fabric_config"]["unit_cell"] = {
            "type": "double_tower", "width_mm": 2, "depth_mm": 3, "height_mm": 4}
        document.metadata["fabric_config"]["placement"] = {
            "spacing_x_mm": 5, "spacing_y_mm": 6}
        with tempfile.TemporaryDirectory() as temporary:
            target = save_pattern_document(document, str(Path(temporary) / "f2.pattern.json"))
            loaded = load_pattern_document(str(target))
        self.assertEqual(loaded.metadata["fabric_config"], document.metadata["fabric_config"])

    def test_api_plan_and_base_stl_share_result_id_but_are_not_fused(self):
        document = configured(rectangle(), "solid")
        document.metadata["fabric_config"]["unit_cell"] = {
            "type": "cone", "width_mm": 2, "depth_mm": 2, "height_mm": 3}
        document.metadata["fabric_config"]["placement"] = {
            "spacing_x_mm": 5, "spacing_y_mm": 5}
        dto = PatternDocumentDTO.from_document(document, "f2-example", 3)
        with TestClient(create_app()) as client:
            built = client.post("/api/v1/manufacturing/build", json=build_payload(dto, .6))
            self.assertEqual(200, built.status_code, built.text)
            result_id = built.json()["manufacturing_result_id"]
            plan = client.get(f"/api/v1/manufacturing/{result_id}/fabric-plan")
            self.assertEqual(200, plan.status_code, plan.text)
            payload = plan.json()
            self.assertEqual(payload["manufacturing_result_id"], result_id)
            self.assertEqual(payload["count"], 80)
            self.assertEqual(payload["manufacturing_status"], "preview_only_not_in_stl")
            self.assertEqual(payload["instances"][0]["z_mm"], .6)
            stl = client.get(f"/api/v1/manufacturing/{result_id}/model.stl")
            glb = client.get(f"/api/v1/manufacturing/{result_id}/preview.glb")
            for response, kind in ((stl, "stl"), (glb, "glb")):
                self.assertEqual(200, response.status_code)
                mesh = trimesh.load(io.BytesIO(response.content), file_type=kind, force="mesh")
                self.assertEqual(tuple(round(value, 5) for value in mesh.extents), (50, 40, .6))
            bad = document.to_dict()
            bad["metadata"]["fabric_config"]["placement"]["spacing_x_mm"] = 0
            invalid = PatternDocumentDTO.from_document(type(document).from_dict(bad), "f2-invalid", 4)
            rejected = client.post("/api/v1/manufacturing/build", json=build_payload(invalid, .6))
            self.assertEqual(422, rejected.status_code)


if __name__ == "__main__":
    unittest.main()
