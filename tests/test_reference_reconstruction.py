from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.reference2d import EditablePatternDocument, analyze_reference2d
from ppg.reference2d.debug_visualization import render_debug
from ppg.exporters import write_editable_document_dxf, write_editable_document_png, write_editable_document_svg
from ppg.model import Project
from ppg.project_io import load_project, save_project


FIXTURES = Path(__file__).parent / "fixtures"


class ReferenceReconstructionTests(unittest.TestCase):
    def test_material_and_example_surfaces_are_removed_from_product_ui(self):
        source = (Path(__file__).parents[1] / "ppg" / "app.py").read_text(encoding="utf-8")
        for token in ("案例库", "素材库", "show_examples", "show_assets", "EXAMPLES", "案例与素材"):
            self.assertNotIn(token, source)

    def test_fixture_detection_outputs_real_editable_elements(self):
        for name in ("test_dot_star.png", "test_dot_gradient.png", "test_dot_grid.png", "test_radial_dot.png", "test_wave_dot.png"):
            with self.subTest(name=name):
                result = analyze_reference2d(str(FIXTURES / name), target_width_mm=100.0)
                document = result.editable_document
                self.assertIsNotNone(document)
                self.assertGreaterEqual(len(document.elements), 8)
                self.assertEqual(len(document.elements), len(result.features))
                for element in document.elements:
                    self.assertTrue({"id", "primitive_type", "x", "y", "width", "height", "radius", "rotation", "opacity", "enabled", "group_id", "source", "confidence"}.issubset(element.to_dict()))
                json.dumps(document.to_dict(), ensure_ascii=False)

    def test_touching_dots_use_distance_watershed_and_stay_separate(self):
        result = analyze_reference2d(str(FIXTURES / "test_touching_dots.png"), target_width_mm=100.0)
        self.assertGreaterEqual(len(result.features), 2)
        self.assertEqual(len(result.editable_document.elements), len(result.features))
        self.assertIsNotNone(result.debug) if result.debug is not None else None
        centers = sorted(element.x for element in result.editable_document.elements)
        self.assertGreater(centers[-1] - centers[0], 8.0)

    def test_low_generator_score_falls_back_to_direct_mode_without_losing_elements(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_star.png"), target_width_mm=100.0)
        document = result.editable_document
        document.generator["mode"] = "direct"; document.generator["base"] = None; document.generator["score"] = 0.1
        self.assertEqual(document.mode, "direct")
        self.assertGreater(len(document.elements), 0)

    def test_element_overrides_survive_batch_operations_and_roundtrip(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document; first = document.elements[0]; document.selected_ids = [item.id for item in document.elements[:4]]
        document.move(document.selected_ids, 2.5, -1.0); document.scale(document.selected_ids, 1.2); document.rotate(document.selected_ids, 10); group_id = document.group()
        self.assertEqual(first.group_id, group_id); self.assertAlmostEqual(document.overrides[first.id]["offset_x"], 2.5)
        clone = document.duplicate([first.id]); self.assertEqual(len(clone), 1); payload = document.to_dict(); restored = EditablePatternDocument.from_dict(payload)
        self.assertEqual(len(restored.elements), len(document.elements)); self.assertEqual(restored.overrides[first.id]["size_scale"], document.overrides[first.id]["size_scale"])

    def test_rebuild_reapplies_local_override_without_raster_readback(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        self.assertEqual(document.mode, "parametric")
        first = document.elements[0]
        initial_x, initial_y = first.x, first.y
        document.move([first.id], 2.5, -1.5)
        document.scale([first.id], 1.25)
        document.rotate([first.id], 12.0)
        before_rebuild = document.element(first.id).to_dict()
        document.rebuild()
        rebuilt = document.element(first.id)
        self.assertAlmostEqual(rebuilt.x, initial_x + 2.5, places=4)
        self.assertAlmostEqual(rebuilt.y, initial_y - 1.5, places=4)
        self.assertAlmostEqual(rebuilt.radius, before_rebuild["radius"], places=4)
        self.assertAlmostEqual(rebuilt.rotation, before_rebuild["rotation"], places=4)
        self.assertEqual(document.metadata["last_rebuild"]["source"], "base_generator+modifier_stack+local_overrides")

    def test_rebuild_preserves_deleted_and_duplicated_elements(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        deleted_id = document.elements[0].id
        duplicate = document.duplicate([document.elements[1].id])[0]
        document.delete([deleted_id])
        document.rebuild()
        ids = {item.id for item in document.elements}
        self.assertNotIn(deleted_id, ids)
        self.assertIn(duplicate.id, ids)
        self.assertTrue(document.overrides[deleted_id]["deleted"])

    def test_direct_mode_rebuild_never_requires_generator_match(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_star.png"), target_width_mm=100.0)
        document = result.editable_document
        document.generator = {"mode": "direct", "base": None, "score": 0.0}
        document.move([document.elements[0].id], 3.0, 0.0)
        expected = document.elements[0].x
        document.rebuild()
        self.assertEqual(document.mode, "direct")
        self.assertAlmostEqual(document.elements[0].x, expected, places=4)

    def test_2d_exports_use_materialized_document_not_reference_bitmap(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        removed = document.elements[0].id
        document.delete([removed]); document.rebuild()
        with TemporaryDirectory() as temp:
            root = Path(temp); svg, png, dxf = root / "result.svg", root / "result.png", root / "result.dxf"
            write_editable_document_svg(str(svg), document)
            write_editable_document_png(str(png), document, size=240)
            write_editable_document_dxf(str(dxf), document)
            self.assertNotIn(removed, svg.read_text(encoding="utf-8"))
            self.assertGreater(png.stat().st_size, 200)
            self.assertIn("GeometryLayer", dxf.read_text(encoding="ascii"))

    def test_project_restore_rebuilds_without_reference_image(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        document.move([document.elements[0].id], 2.0, 1.0)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "editable.ppg"
            project = Project(name="Editable restore", editable_pattern_document=document.to_dict())
            save_project(str(path), project)
            restored = EditablePatternDocument.from_dict(load_project(str(path)).editable_pattern_document or {})
            restored.rebuild()
            self.assertEqual(len(restored.elements), len(document.elements))
            self.assertAlmostEqual(restored.elements[0].x, document.elements[0].x, places=4)

    def test_parametric_rule_change_rebuilds_and_keeps_local_offset(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        self.assertEqual(document.mode, "parametric")
        target = document.elements[-1]
        base = next(item for item in document.base_elements if item.id == target.id)
        document.move([target.id], 4.0, 0.0)
        params = document.generator["parameters"]
        params["scale_x"] = 1.35
        document.rebuild()
        expected = params["origin_x"] + document.generator["bindings"][target.id]["u"] * params["spacing_x"] * 1.35 + 4.0
        self.assertAlmostEqual(document.element(target.id).x, expected, places=4)
        self.assertNotAlmostEqual(document.element(target.id).x, base.x + 4.0, places=4)

    def test_modifier_stack_materializes_density_rotation_warp_and_mask_without_raster(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        self.assertEqual(document.mode, "parametric")
        target = document.elements[-1]
        before = target.to_dict()
        for modifier in document.modifiers:
            params = modifier["parameters"]
            if modifier["name"] == "DensityField":
                params.update(enabled=True, strength=.6)
            elif modifier["name"] == "RotationField":
                params.update(enabled=True, strength=30.0)
            elif modifier["name"] == "SimpleWarp":
                params.update(enabled=True, amplitude=4.0, frequency=1.0)
            elif modifier["name"] == "Mask":
                params.update(enabled=True, radius=100.0)
        document.rebuild()
        rebuilt = document.element(target.id)
        self.assertLess(rebuilt.opacity, before["opacity"])
        self.assertNotAlmostEqual(rebuilt.rotation, before["rotation"], places=4)
        self.assertNotAlmostEqual(rebuilt.x, before["x"], places=4)
        self.assertEqual(document.metadata["last_rebuild"]["source"], "base_generator+modifier_stack+local_overrides")

    def test_rectangle_selection_is_editable_and_additive(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_grid.png"), target_width_mm=100.0)
        document = result.editable_document
        selected = document.select_rect(0.0, 0.0, 50.0, 50.0)
        self.assertGreater(len(selected), 0)
        selected_ids = list(document.selected_ids)
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        added = document.select_rect(50.0, 50.0, 100.0, 100.0, additive=True)
        self.assertGreater(len(added), 0)
        self.assertGreater(len(document.selected_ids), len(selected_ids))

    def test_debug_visualization_writes_detection_evidence(self):
        result = analyze_reference2d(str(FIXTURES / "test_dot_gradient.png"), debug={})
        self.assertTrue(result.debug and "distance_transform" in result.debug and "watershed_labels" in result.debug)
        target = FIXTURES / "_debug_detection.png"
        try:
            render_debug(result.preprocessed, result.features, result.debug, target)
            self.assertGreater(target.stat().st_size, 100)
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__": unittest.main()
