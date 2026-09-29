"""Web actions must use the same Session semantics as desktop buttons."""
import unittest
from math import cos, pi, sin
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from ppg.foundation import FoundationPipeline
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fixtures import build_fixed_suite
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.web import create_app


def document(points):
    elements = [CircleElement(id=f"dot-{index}", x=x, y=y, width=4, height=4,
                              style={"fill": "#000000"}) for index, (x, y) in enumerate(points)]
    source = PatternDocument(Canvas(200, 200, unit="mm", mm_per_unit=1), Reference(""), elements)
    return PatternDocumentDTO.from_document(source, "desktop-align", 0).to_dict()


class WebDesktopParametricAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def tearDown(self):
        self.client.close()

    def action(self, dto, name):
        return self.client.post("/api/v1/pattern-action", json={
            "document": dto, "document_revision": dto["document_revision"], "action": name,
        })

    def test_analysis_is_read_only_and_convert_is_explicit(self):
        original = document([(10 + c * 10, 10 + r * 10) for r in range(6) for c in range(6)])
        response = self.client.post("/api/v1/analyze-pattern", json={"document": original})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recommended_family"], "grid")
        self.assertEqual(original["document_revision"], 0)
        converted_response = self.action(original, "convert_recommended")
        self.assertEqual(converted_response.status_code, 200, converted_response.text)
        converted = converted_response.json()
        self.assertEqual(converted["document_revision"], 1)
        self.assertEqual(converted["document"]["metadata"]["xiaomang_pattern_lab.parametric"]["family"], "grid")
        self.assertEqual(len(converted["document"]["elements"]), 36)
        baked_response = self.action(converted, "bake")
        self.assertEqual(baked_response.status_code, 200, baked_response.text)
        baked = baked_response.json()
        self.assertEqual(baked["document_revision"], 2)
        self.assertNotIn("xiaomang_pattern_lab.parametric", baked["document"]["metadata"])
        self.assertEqual(len(baked["document"]["elements"]), 36)

    def test_free_preserves_irregular_positions_and_has_explicit_no_match(self):
        original = document([(3, 7), (41, 96), (83, 12), (161, 57), (204, 154), (287, 35), (320, 226)])
        before = [(item["x"], item["y"]) for item in original["document"]["elements"]]
        self.assertEqual(self.action(original, "convert_recommended").status_code, 422)
        free_response = self.action(original, "enter_free")
        self.assertEqual(free_response.status_code, 200, free_response.text)
        free = free_response.json()
        self.assertEqual([(item["x"], item["y"]) for item in free["document"]["elements"]], before)
        self.assertEqual(free["document"]["metadata"]["xiaomang_pattern_lab.parametric"]["family"], "free_parametric")
        self.assertEqual(self.action(original, "bake").status_code, 422)
        self.assertEqual(self.action(original, "unknown").status_code, 422)

    def test_radial_and_curve_use_existing_session_families(self):
        cases = (
            ("radial", [(100 + cos(2 * pi * i / 12) * 52,
                         100 + sin(2 * pi * i / 12) * 52) for i in range(12)]),
            ("along_curve", [(100 + cos(-1.2 + i * .2) * 75,
                              90 + sin(-1.2 + i * .2) * 75) for i in range(11)]),
        )
        for family, centers in cases:
            with self.subTest(family=family):
                original = document(centers)
                response = self.action(original, "convert_recommended")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["document"]["metadata"]
                                 ["xiaomang_pattern_lab.parametric"]["family"], family)

    def test_imported_png_matches_desktop_session_conversion(self):
        image = build_fixed_suite()["regular_dot_matrix"].read_bytes()
        upload = self.client.post("/api/v1/assets", content=image,
                                  headers={"Content-Type": "image/png", "X-Filename": "dots.png"})
        self.assertEqual(upload.status_code, 200, upload.text)
        imported = self.client.post("/api/v1/import", json={"asset_id": upload.json()["asset_id"]}).json()
        self.assertEqual(self.client.post("/api/v1/analyze-pattern", json={"document": imported})
                         .json()["recommended_family"], "grid")
        with TemporaryDirectory() as temp:
            desktop = PatternLabSession(FoundationPipeline(None, None), Path(temp),
                                        document=PatternDocumentDTO.from_dict(imported).to_document())
            recommendation = desktop.analyze_families().recommended
            desktop.activate_grid(recommendation.model)
            web = self.action(imported, "convert_recommended")
            self.assertEqual(web.status_code, 200, web.text)
            self.assertEqual(web.json()["document"], desktop.require_document().to_dict())


if __name__ == "__main__":
    unittest.main()
