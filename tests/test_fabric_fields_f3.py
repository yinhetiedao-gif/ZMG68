"""F3 field-driven Fabric instances remain preview-only and deterministic."""
from __future__ import annotations

from copy import deepcopy
from time import perf_counter
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ppg.foundation import Canvas, PatternDocument, RectElement, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_field_modifiers import apply_fabric_field_modifiers
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.shared_fields import (CheckerField, CompositeField, ConstantField, FieldMapping,
    LinearField, NoiseField, RingField, RotationModifier, SizeModifier, SpiralField, StripeField, WaveField)
from xiaomang_pattern_lab.web import create_app


def document_with_fabric(count=20, cell_type="fin"):
    elements = [RectElement(f"square-{index}", 5 + index % 13 * 5,
                            5 + index // 13 * 5, 2, 2) for index in range(count)]
    document = PatternDocument(Canvas(80, 80, "mm", 1), Reference("", False), elements)
    document.metadata["fabric_config"] = {
        "config_version": 1,
        "base": {"type": "solid", "thickness_mm": .6, "margin_mm": 0},
        "unit_cell": {"type": cell_type, "width_mm": 2, "depth_mm": 2, "height_mm": 3},
        "placement": {"mode": "pattern_points", "spacing_x_mm": 5, "spacing_y_mm": 5}}
    return document


def preview(document, revision=1):
    dto = PatternDocumentDTO.from_document(document, "f3-test", revision)
    with TestClient(create_app()) as client, patch(
            "xiaomang_pattern_lab.manufacturing_service.ManufacturingService.build",
            side_effect=AssertionError("Fabric preview entered manufacturing")):
        response = client.post("/api/v1/fabric/preview", json={
            "document": dto.to_dict(), "document_revision": revision})
    return response


class FabricFieldsF3Tests(unittest.TestCase):
    def test_python_parameter_schema_defines_all_four_fabric_controls(self):
        definitions = parameter_definitions()["definitions"]["fabric_modifier"]
        self.assertEqual(set(definitions), {"height", "scale", "density", "orientation"})
        self.assertEqual({item["id"] for item in definitions["height"]["parameters"]},
                         {"min_height_mm", "max_height_mm"})

    def test_wave_drives_height_without_moving_xy_or_mutating_document(self):
        document = document_with_fabric()
        document.fields = [WaveField("wave", wavelength=40).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "height": {"enabled": True, "field_id": "wave",
                       "min_height_mm": 1, "max_height_mm": 5}}
        before = deepcopy(document.to_dict())
        response = preview(document)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["active_count"], 20)
        self.assertGreater(max(item["height_mm"] for item in result["instances"])
                           - min(item["height_mm"] for item in result["instances"]), 1)
        self.assertTrue(all(1 <= item["height_mm"] <= 5 for item in result["instances"]))
        for item, source in zip(result["instances"], document.elements):
            self.assertEqual((item["x_mm"], item["y_mm"]), (source.x, source.y))
            self.assertEqual(item["base_height_mm"], 3)
        self.assertEqual(document.to_dict(), before)

    def test_linear_scale_multiplies_pattern_scale_once(self):
        document = document_with_fabric()
        document.fields = [LinearField("linear", angle=0).to_dict(),
                           ConstantField("constant", .75).to_dict()]
        document.modifiers = [SizeModifier("pattern-size", "constant", FieldMapping(1.4, 1.4)).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "scale": {"enabled": True, "field_id": "linear",
                      "min_scale": .5, "max_scale": 1.5}}
        result = preview(document).json()
        self.assertEqual(result["total_count"], 20)
        self.assertEqual(result["instances"][0]["scale_x"], 1.4)
        self.assertAlmostEqual(result["instances"][0]["scale"], .5)
        rightmost = max(result["instances"], key=lambda item: item["x_mm"])
        self.assertAlmostEqual(rightmost["scale"], 1.5)
        self.assertEqual(result["instances"][0]["height_mm"], 3)

    def test_noise_density_is_deterministic_and_does_not_change_placement(self):
        document = document_with_fabric(169)
        document.fields = [NoiseField("noise", scale=17, seed=42).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "density": {"enabled": True, "field_id": "noise", "threshold": .5}}
        first = preview(document).json()
        second = preview(document).json()
        a = [(item["id"], item["enabled"], item["x_mm"], item["y_mm"])
             for item in first["instances"]]
        b = [(item["id"], item["enabled"], item["x_mm"], item["y_mm"])
             for item in second["instances"]]
        self.assertEqual(a, b)
        self.assertEqual(first["active_count"], sum(item[1] for item in a))
        self.assertGreater(first["active_count"], 0)
        self.assertLess(first["active_count"], 169)

    def test_fin_orientation_adds_to_final_pattern_rotation(self):
        document = document_with_fabric(cell_type="fin")
        document.fields = [LinearField("linear", angle=0).to_dict(),
                           WaveField("wave", wavelength=40).to_dict()]
        document.modifiers = [RotationModifier("pattern-rotate", "wave", FieldMapping(30, 30)).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "orientation": {"enabled": True, "field_id": "linear",
                            "min_angle_deg": -45, "max_angle_deg": 45}}
        result = preview(document).json()
        self.assertAlmostEqual(result["instances"][0]["rotation_deg"], -15)
        rightmost = max(result["instances"], key=lambda item: item["x_mm"])
        self.assertAlmostEqual(rightmost["rotation_deg"], 75)

    def test_one_wave_field_drives_height_and_scale_with_composite_supported(self):
        document = document_with_fabric()
        document.fields = [WaveField("wave", wavelength=40).to_dict(),
                           LinearField("linear", angle=0).to_dict(),
                           CompositeField("combined", "wave", "linear", "multiply").to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "height": {"enabled": True, "field_id": "wave",
                       "min_height_mm": 1, "max_height_mm": 5},
            "scale": {"enabled": True, "field_id": "wave",
                      "min_scale": .5, "max_scale": 1.5},
            "density": {"enabled": True, "field_id": "combined", "threshold": .1}}
        result = preview(document).json()
        self.assertEqual(result["total_count"], 20)
        for item in result["instances"]:
            value = (item["height_mm"] - 1) / 4
            self.assertAlmostEqual(item["scale"], .5 + value)

    def test_all_existing_supported_field_types_feed_fabric_without_manufacturing(self):
        field_types = (ConstantField, LinearField, WaveField, RingField,
                       StripeField, CheckerField, SpiralField, NoiseField)
        for field_type in field_types:
            with self.subTest(field=field_type.__name__):
                document = document_with_fabric()
                document.fields = [field_type("field").to_dict()]
                document.metadata["fabric_config"]["field_modifiers"] = {
                    "height": {"enabled": True, "field_id": "field",
                               "min_height_mm": 1, "max_height_mm": 5}}
                response = preview(document)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["total_count"], 20)

    def test_pattern_points_combined_keeps_final_pattern_transform(self):
        document = document_with_fabric()
        document.fields = [ConstantField("constant", .5).to_dict(),
                           LinearField("linear", angle=0).to_dict()]
        document.modifiers = [
            SizeModifier("pattern-size", "constant", FieldMapping(1.4, 1.4)).to_dict(),
            RotationModifier("pattern-rotation", "constant", FieldMapping(30, 30)).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "height": {"enabled": True, "field_id": "linear", "min_height_mm": 1, "max_height_mm": 5},
            "scale": {"enabled": True, "field_id": "linear", "min_scale": .5, "max_scale": 1.5},
            "orientation": {"enabled": True, "field_id": "constant", "min_angle_deg": 15, "max_angle_deg": 15}}
        result = preview(document).json()
        self.assertEqual(result["placement_mode"], "pattern_points")
        self.assertEqual(result["total_count"], 20)
        first = result["instances"][0]
        self.assertEqual((first["x_mm"], first["y_mm"]), (document.elements[0].x, document.elements[0].y))
        self.assertAlmostEqual(first["scale_x"], 1.4)
        self.assertAlmostEqual(first["scale"], .5)
        self.assertAlmostEqual(first["rotation_deg"], 45)
        self.assertEqual(first["height_mm"], 1)

    def test_area_fill_and_invalid_values(self):
        document = document_with_fabric()
        document.metadata["fabric_config"]["placement"]["mode"] = "area_fill"
        document.fields = [ConstantField("constant", .25).to_dict()]
        document.metadata["fabric_config"]["field_modifiers"] = {
            "height": {"enabled": True, "field_id": "constant",
                       "min_height_mm": 1, "max_height_mm": 5}}
        result = preview(document).json()
        self.assertEqual(result["placement_mode"], "area_fill")
        self.assertTrue(all(item["height_mm"] == 2 for item in result["instances"]))
        document.metadata["fabric_config"]["field_modifiers"]["height"]["min_height_mm"] = 0
        response = preview(document, 2)
        self.assertEqual(response.status_code, 422)
        self.assertIn("min_height_mm", response.text)

    def test_plan_scaling_100_to_5000_has_no_mesh_work(self):
        document = document_with_fabric()
        document.fields = [LinearField("linear", angle=0).to_dict()]
        config = {"height": {"enabled": True, "field_id": "linear",
                             "min_height_mm": 1, "max_height_mm": 5}}
        cell = UnitCellDefinition("fin", 2, 2, 3)
        timings = {}
        for count in (100, 400, 1000, 5000):
            started = perf_counter()
            plan = FabricPlanner().plan((0, 0, count, 1), .6, cell, RegularPlacement(1, 1))
            result = apply_fabric_field_modifiers(plan, document, config)
            result.preview_payload()
            timings[count] = round((perf_counter() - started) * 1000, 3)
            self.assertEqual(result.count, count)
            self.assertEqual(result.instances[0].height_mm, 1)
            self.assertEqual(result.instances[-1].height_mm, 5)
        print("F3 plan+field+serialization ms:", timings)


if __name__ == "__main__":
    unittest.main()
