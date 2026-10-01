"""F2.5: preview must not depend on manufacturing, and points use final mm geometry."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ppg.foundation import Canvas, PatternDocument, RectElement, Reference
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.contracts.v1 import final_geometry
from xiaomang_pattern_lab.faithful_mapping import FaithfulMappingAdapter
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.shared_modifiers import PositionModifier, SharedModifierStack
from xiaomang_pattern_lab.shared_fields import (DensityModifier, FieldMapping,
    FieldPositionModifier, LinearField, RotationModifier, SizeModifier,
    SpiralField, WaveField)
from xiaomang_pattern_lab.web import create_app


def document_with_points(count: int) -> PatternDocument:
    elements = [RectElement(f"square-{index}", 5 + index % 20 * 5,
                            5 + index // 20 * 5, 2, 2) for index in range(count)]
    document = PatternDocument(Canvas(120, 120, "mm", 1), Reference("", False), elements)
    document.metadata["fabric_config"] = {
        "config_version": 1, "base": {"type": "solid", "thickness_mm": .6, "margin_mm": 0},
        "unit_cell": {"type": "cone", "width_mm": 2, "depth_mm": 2, "height_mm": 3},
        "placement": {"mode": "pattern_points", "spacing_x_mm": 5, "spacing_y_mm": 5}}
    return document


def preview(client, document, revision=1):
    dto = PatternDocumentDTO.from_document(document, "fabric-preview-test", revision)
    return client.post("/api/v1/fabric/preview", json={
        "document": dto.to_dict(), "document_revision": revision})


class FabricPreviewF25Tests(unittest.TestCase):
    def test_position_stack_follows_final_center_without_double_scaling(self):
        document = document_with_points(20)
        stack = SharedModifierStack(source_elements=document.elements)
        stack.add_modifier("position", PositionModifier(mode="offset", offset_x=7,
                                                        offset_y=-3).to_dict())
        stack.attach(document)
        source = {item.id: (item.x, item.y) for item in document.elements}
        with TestClient(create_app()) as client:
            result = preview(client, document).json()
        self.assertEqual(result["total_count"], 20)
        self.assertEqual(result["unmatched_reference_count"], 0)
        for item in result["instances"]:
            x, y = source[item["source_id"]]
            self.assertAlmostEqual(item["x_mm"], x + 7)
            self.assertAlmostEqual(item["y_mm"], y - 3)
            self.assertEqual((item["scale_x"], item["scale_y"]), (1, 1))

    def test_pattern_points_20_and_stale_revision(self):
        document = document_with_points(20)
        with TestClient(create_app()) as client, patch(
                "xiaomang_pattern_lab.manufacturing_service.ManufacturingService.build",
                side_effect=AssertionError("preview entered full manufacturing")):
            response = preview(client, document)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data["count"], 20)
            self.assertEqual(data["total_count"], 20)
            self.assertEqual(data["placement_mode"], "pattern_points")
            self.assertEqual(data["instances"][0]["source_id"], "square-0")
            self.assertEqual((data["instances"][0]["x_mm"], data["instances"][0]["y_mm"]), (5, 5))
            self.assertEqual(data["instances"][0]["z_mm"], .6)
            self.assertFalse(data["cache_hit"])
            self.assertTrue(preview(client, document).json()["cache_hit"])
            document.elements[0].x += 1
            updated = preview(client, document, 2).json()
            self.assertEqual(updated["instances"][0]["x_mm"], 6)
            self.assertFalse(updated["cache_hit"])

    def test_actual_169_square_image_positions(self):
        fixture = Path(__file__).parent / "fixtures" / "field_manufacturing_matrix_169.jpg"
        with TemporaryDirectory() as temporary:
            document = FaithfulMappingAdapter(BinaryThresholdImageProcessingAdapter(),
                ImageToSVGVectorizationAdapter(mode="simple")).map_raster(
                    str(fixture), str(Path(temporary) / "matrix.svg")).document
            document.canvas.mm_per_unit = 1.0
            document.reference.source_path = ""
            document.reference.metadata["preprocessed_path"] = ""
            document.metadata["source_svg"] = ""
            document.metadata["fabric_config"] = document_with_points(1).metadata["fabric_config"]
            with TestClient(create_app()) as client:
                response = preview(client, document)
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["element_count"], 169)
            self.assertEqual(result["total_count"], 169)
            actual = {item["source_id"]: (item["x_mm"], item["y_mm"]) for item in result["instances"]}
            for element in document.elements:
                self.assertEqual(actual[element.id], (element.x, element.y))

            document.fields = [WaveField("wave", wavelength=80).to_dict(),
                               SpiralField("spiral", center_x=171.5, center_y=172, turns=2).to_dict()]
            document.modifiers = [
                SizeModifier("size", "wave", FieldMapping(.5, 1.5)).to_dict(),
                RotationModifier("rotate", "spiral", FieldMapping(-45, 45)).to_dict(),
                FieldPositionModifier("move", "wave", FieldMapping(-8, 8), FieldMapping(-4, 4)).to_dict(),
            ]
            before = PatternDocumentDTO.from_document(document, "combined", 1).to_dict()
            final, _ = final_geometry(document)
            with TestClient(create_app()) as client:
                combined = preview(client, document, revision=16).json()
            self.assertEqual(combined["document_revision"], 16)
            self.assertEqual(combined["total_count"], 169)
            self.assertEqual(combined["unmatched_reference_count"], 0)
            original = {element.id: element for element in document.elements}
            instances = {item["final_geometry_id"]: item for item in combined["instances"]}
            self.assertEqual(set(instances), {item["id"] for item in final})
            for item in final:
                instance = instances[item["id"]]
                source = original[item["id"]]
                self.assertEqual(instance["source_id"], item["id"])
                self.assertAlmostEqual(instance["x_mm"], item["x"])
                self.assertAlmostEqual(instance["y_mm"], item["y"])
                self.assertAlmostEqual(instance["scale_x"], item["width"] / source.width)
                self.assertAlmostEqual(instance["scale_y"], item["height"] / source.height)
                self.assertAlmostEqual(instance["rotation_deg"], item["rotation"])
                self.assertTrue(instance["enabled"])
            self.assertTrue(any(abs(item["scale_x"] - 1) > .1 for item in instances.values()))
            self.assertTrue(any(abs(item["rotation_deg"]) > 1 for item in instances.values()))
            self.assertTrue(any(abs(item["x_mm"] - original[item["source_id"]].x) > 1
                                for item in instances.values()))
            self.assertEqual(PatternDocumentDTO.from_document(document, "combined", 1).to_dict(), before)

    def test_visibility_filters_instances_from_final_geometry(self):
        document = document_with_points(20)
        document.fields = [LinearField("linear", angle=0).to_dict()]
        document.modifiers = [DensityModifier("density", "linear", threshold=.5).to_dict()]
        final, _ = final_geometry(document)
        self.assertGreater(len(final), 0)
        self.assertLess(len(final), 20)
        with TestClient(create_app()) as client:
            result = preview(client, document).json()
        self.assertEqual(result["total_count"], len(final))
        self.assertEqual({item["final_geometry_id"] for item in result["instances"]},
                         {item["id"] for item in final})
        self.assertTrue(all(item["enabled"] for item in result["instances"]))

    def test_area_fill_and_large_preview_sampling(self):
        document = document_with_points(20)
        document.metadata["fabric_config"]["placement"]["mode"] = "area_fill"
        document.metadata["fabric_config"]["placement"]["spacing_y_mm"] = 1
        with TestClient(create_app()) as client:
            result = preview(client, document).json()
        self.assertEqual(result["placement_mode"], "area_fill")
        self.assertGreater(result["count"], 0)
        cell = UnitCellDefinition("fin", 1, 1, 2)
        for count in (100, 400, 1000, 5000):
            plan = FabricPlanner().plan((0, 0, count, 1), .6, cell, RegularPlacement(1, 1))
            self.assertEqual(plan.count, count)
            self.assertEqual(plan.total_count, count)
        sampled = FabricPlanner().plan((0, 0, 10000, 1), .6, cell, RegularPlacement(1, 1))
        self.assertEqual(sampled.total_count, 10000)
        self.assertEqual(sampled.count, 5000)
        self.assertTrue(sampled.preview_payload()["preview_simplified"])
        near_cap = FabricPlanner().plan((0, 0, 5041, 1), .6, cell, RegularPlacement(1, 1))
        self.assertEqual(near_cap.total_count, 5041)
        self.assertEqual(near_cap.count, 5000)


if __name__ == "__main__":
    unittest.main()
