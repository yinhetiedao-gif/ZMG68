"""Acceptance tests for the upstream Raster → SVG → editable layer loop."""
from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from ppg.upstream_svg_pipeline import EditableSVGDocument, ImageToSVGClient, sha256_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUT = ROOT / "work" / "upstream-svg-integration"


class UpstreamSVGIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = ImageToSVGClient(timeout=180)
        if not cls.client.available:
            raise unittest.SkipTest("external imagetosvg-mcp 未构建")
        OUT.mkdir(parents=True, exist_ok=True)

    def _run_case(self, fixture_name: str) -> dict:
        image = FIXTURES / fixture_name
        stem = image.stem
        svg = OUT / (stem + ".svg")
        if svg.exists():
            svg.unlink()
        conversion = self.client.convert_image_to_svg(str(image), str(svg), mode="simple")
        self.assertTrue(svg.is_file(), "Raster 转换没有生成 SVG：%s" % fixture_name)
        root = ET.parse(str(svg)).getroot()
        self.assertEqual(root.attrib.get("xmlns") or root.tag.rsplit("}", 1)[0].strip("{"),
                         "http://www.w3.org/2000/svg")
        self.assertTrue(root.attrib.get("viewBox"), "SVG 缺少 viewBox：%s" % fixture_name)
        inspect = self.client.inspect_svg(str(svg))
        self.assertGreater(int(inspect.get("layerCount", 0)), 0)
        if isinstance(conversion.get("summary"), dict):
            conversion["summary"]["viewBox"] = inspect.get("viewBox")
        document = EditableSVGDocument.from_inspection(str(image), str(svg), inspect)
        self.assertEqual(len(document.elements), int(inspect["layerCount"]))
        self.assertTrue(document.reference_visible)
        document.hide_reference()
        self.assertFalse(document.reference_visible)
        editable_json = OUT / (stem + ".editable.json")
        editable_json.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(editable_json.is_file())

        before = document.render(self.client, width=512)
        preview = Path(before["previewPath"])
        self.assertTrue(preview.is_file(), "SVG 无法重新渲染：%s" % fixture_name)
        before_hash = sha256_file(str(preview))

        first_id = document.elements[0].id
        document.edit(self.client, first_id, translate=[7.0, 3.0], scale=1.25)
        after = document.render(self.client, width=512)
        after_preview = Path(after["previewPath"])
        self.assertTrue(after_preview.is_file())
        self.assertNotEqual(before_hash, sha256_file(str(after_preview)),
                            "编辑元素后渲染图没有可见变化：%s" % fixture_name)

        optimized = OUT / (stem + ".optimized.svg")
        self.client.optimize_svg(str(svg), str(optimized))
        self.assertTrue(optimized.is_file())
        optimized_inspect = self.client.inspect_svg(str(optimized))
        self.assertGreater(int(optimized_inspect.get("layerCount", 0)), 0)
        return {
            "fixture": fixture_name,
            "svg": str(svg),
            "optimized_svg": str(optimized),
            "editable_json": str(editable_json),
            "element_count": len(document.elements),
            "first_element": first_id,
            "reference_hidden": not document.reference_visible,
            "before_preview": str(preview),
            "after_preview": str(after_preview),
            "render_changed": before_hash != sha256_file(str(after_preview)),
            "conversion": conversion,
        }

    def test_regular_dot_grid(self):
        self._run_case("test_dot_grid.png")

    def test_gradient_halftone(self):
        self._run_case("test_dot_gradient.png")

    def test_star_mask_pattern(self):
        self._run_case("test_dot_star.png")

    def test_write_report(self):
        reports = []
        for fixture in ("test_dot_grid.png", "test_dot_gradient.png", "test_dot_star.png"):
            reports.append(self._run_case(fixture))
        report = OUT / "integration-report.json"
        report.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(report.is_file())


if __name__ == "__main__":
    unittest.main()
