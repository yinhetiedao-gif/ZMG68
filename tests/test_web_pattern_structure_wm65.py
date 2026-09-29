"""WM6.5: Web imports and family conversion use the existing desktop analyzer."""
from __future__ import annotations

from math import cos, pi, sin
from dataclasses import replace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fixtures import build_fixed_suite
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.pattern_analyzer import MultiFamilyAnalysis, PatternAnalyzer
from xiaomang_pattern_lab.web import create_app


def dot(identifier, x, y):
    return CircleElement(id=identifier, x=x, y=y, width=6, height=6,
                         style={"fill": "#000000"})


def dto(elements):
    document = PatternDocument(Canvas(400, 400, unit="mm", mm_per_unit=1), Reference(""), elements)
    return PatternDocumentDTO.from_document(document, "wm65-test", 0).to_dict()


class WebPatternStructureWM65Tests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def tearDown(self):
        self.client.close()

    def analyze(self, document):
        response = self.client.post("/api/v1/analyze-pattern", json={"document": document})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def apply(self, document, family):
        return self.client.post("/api/v1/apply-pattern", json={
            "document": document, "document_revision": document["document_revision"], "family": family,
        })

    def test_grid_radial_curve_and_free_fallback(self):
        grid = dto(GridParametricModel(rows=6, columns=8, spacing_x=18,
                                       spacing_y=21, offset_x=70, offset_y=85).generate())
        radial = dto([dot("r%d" % i, 100 + cos(2 * pi * i / 12) * 52,
                          100 + sin(2 * pi * i / 12) * 52) for i in range(12)])
        curve = dto([dot("c%d" % i, 100 + cos(-1.2 + i * .2) * 75,
                         90 + sin(-1.2 + i * .2) * 75) for i in range(11)])
        irregular = dto([dot("i%d" % i, x, y) for i, (x, y) in enumerate(
            ((3, 7), (41, 96), (83, 12), (161, 57), (204, 154), (287, 35), (320, 226)))])
        for document, family in ((grid, "grid"), (radial, "radial"),
                                 (curve, "along_curve"), (irregular, "free")):
            with self.subTest(family=family):
                result = self.analyze(document)
                self.assertEqual(result["recommended_family"], None if family == "free" else family)
                self.assertEqual(result["analysis_status"], "no_match" if family == "free" else "matched")
                response = self.apply(document, family)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn("xiaomang-pattern-", response.text)
                converted = response.json()
                self.assertEqual(converted["document_revision"], 1)
                self.assertEqual(converted["document"]["metadata"]["xiaomang_pattern_lab.parametric"]["family"],
                                 "free_parametric" if family == "free" else family)
                evaluated = self.client.post("/api/v1/evaluate", json={
                    "schema_version": "1.0", "document_id": converted["document_id"],
                    "document_revision": 1, "document": converted,
                })
                self.assertEqual(evaluated.status_code, 200, evaluated.text)
                self.assertGreater(len(evaluated.json()["geometry"]), 0)

    def test_unavailable_family_rejected_and_revision_guarded(self):
        document = dto([dot("a", 10, 10), dot("b", 61, 22)])
        response = self.apply(document, "grid")
        self.assertEqual(response.status_code, 422)
        self.assertIn("无法应用该图案结构", response.json()["message"])
        self.assertEqual(self.client.post("/api/v1/apply-pattern", json={
            "document": document, "document_revision": 99, "family": "free",
        }).status_code, 409)

    def test_real_imported_png_and_svg_enter_same_analyzer(self):
        fixtures = build_fixed_suite()
        for filename, media_type, data in (
            ("regular.png", "image/png", fixtures["regular_dot_matrix"].read_bytes()),
            ("dots.svg", "image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
             b'<circle cx="20" cy="20" r="4"/><circle cx="40" cy="20" r="4"/>'
             b'<circle cx="20" cy="40" r="4"/><circle cx="40" cy="40" r="4"/></svg>'),
        ):
            with self.subTest(filename=filename):
                upload = self.client.post("/api/v1/assets", content=data,
                                          headers={"Content-Type": media_type, "X-Filename": filename})
                self.assertEqual(upload.status_code, 200, upload.text)
                imported = self.client.post("/api/v1/import", json={"asset_id": upload.json()["asset_id"]})
                self.assertEqual(imported.status_code, 200, imported.text)
                document = imported.json()
                self.assertGreater(len(document["document"]["elements"]), 0)
                analysis = self.analyze(document)
                self.assertEqual(analysis["document_id"], document["document_id"])
                if media_type == "image/png":
                    self.assertEqual(analysis["recommended_family"], "grid")

    def test_imported_radial_and_curve_svg_enable_matching_family(self):
        for family, centers in (
            ("radial", [(100 + cos(2 * pi * i / 12) * 52,
                         100 + sin(2 * pi * i / 12) * 52) for i in range(12)]),
            ("along_curve", [(100 + cos(-1.2 + i * .2) * 75,
                              90 + sin(-1.2 + i * .2) * 75) for i in range(11)]),
        ):
            with self.subTest(family=family):
                circles = "".join('<circle cx="%s" cy="%s" r="3" fill="black"/>' % (x, y)
                                  for x, y in centers)
                svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300">%s</svg>'
                       % circles).encode("utf-8")
                upload = self.client.post("/api/v1/assets", content=svg,
                                          headers={"Content-Type": "image/svg+xml", "X-Filename": family + ".svg"})
                self.assertEqual(upload.status_code, 200, upload.text)
                imported = self.client.post("/api/v1/import", json={"asset_id": upload.json()["asset_id"]})
                self.assertEqual(imported.status_code, 200, imported.text)
                document = imported.json()
                analysis = self.analyze(document)
                self.assertEqual(analysis["recommended_family"], family)
                self.assertEqual(self.apply(document, family).status_code, 200)

    def test_low_confidence_is_not_an_application_gate(self):
        document = dto(GridParametricModel(rows=6, columns=8, spacing_x=18,
                                          spacing_y=21, offset_x=70, offset_y=85).generate())
        actual = PatternAnalyzer().analyze_families(PatternDocument.from_dict(document["document"]).elements)
        low_grid = replace(actual.candidate("grid"), confidence=0.1)
        low = MultiFamilyAnalysis((low_grid, *actual.candidates[1:]), None, actual.fallback)
        with patch("xiaomang_pattern_lab.web.app.PatternAnalyzer") as analyzer:
            analyzer.return_value.analyze_families.return_value = low
            response = self.apply(document, "grid")
        self.assertEqual(response.status_code, 200, response.text)

    def test_free_is_available_for_empty_document(self):
        document = dto([])
        response = self.apply(document, "free")
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()
