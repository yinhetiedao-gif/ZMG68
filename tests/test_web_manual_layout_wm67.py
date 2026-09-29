"""Recognition recommends; manual layout uses the existing parametric models."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.web import create_app


def irregular_document():
    points = [(3, 7), (41, 96), (83, 12), (161, 57), (204, 154), (287, 35), (320, 226)]
    elements = [CircleElement(id="i%d" % index, x=x, y=y, width=6, height=6,
                              style={"fill": "#000000"})
                for index, (x, y) in enumerate(points)]
    document = PatternDocument(Canvas(400, 400, unit="mm", mm_per_unit=1), Reference(""), elements)
    return PatternDocumentDTO.from_document(document, "manual-layout-test", 0).to_dict()


class WebManualLayoutWM67Tests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        self.document = irregular_document()

    def tearDown(self):
        self.client.close()

    def prepare(self, family, parameters=None):
        body = {"document": self.document, "document_revision": 0, "family": family}
        if parameters is not None:
            body["parameters"] = parameters
        return self.client.post("/api/v1/prepare-pattern", json=body)

    def test_irregular_source_can_prepare_three_manual_layouts_without_mutation(self):
        before = self.document["document"]
        for family in ("grid", "radial", "along_curve"):
            with self.subTest(family=family):
                result = self.prepare(family)
                self.assertEqual(result.status_code, 200, result.text)
                prepared = result.json()
                self.assertEqual(prepared["mode"], "manual")
                self.assertEqual(prepared["proposed_document"]["document_revision"], 1)
                self.assertGreater(len(prepared["proposed_document"]["document"]["elements"]), 0)
                self.assertTrue(prepared["preview"]["geometry"])
                self.assertEqual(self.document["document"], before)
                proposal = prepared["proposed_document"]
                evaluation = self.client.post("/api/v1/evaluate", json={
                    "schema_version": "1.0", "document_id": proposal["document_id"],
                    "document_revision": proposal["document_revision"], "document": proposal})
                self.assertEqual(evaluation.status_code, 200, evaluation.text)
                self.assertTrue(evaluation.json()["geometry"])

    def test_manual_parameters_change_existing_models(self):
        grid = self.prepare("grid", {"rows": 3, "columns": 4, "spacing_x": 20, "spacing_y": 25})
        self.assertEqual(grid.status_code, 200, grid.text)
        self.assertEqual(len(grid.json()["proposed_document"]["document"]["elements"]), 12)
        radial = self.prepare("radial", {"count": 10, "radius": 42, "angular_offset": 30})
        self.assertEqual(radial.status_code, 200, radial.text)
        self.assertEqual(len(radial.json()["proposed_document"]["document"]["elements"]), 10)
        curve = self.prepare("along_curve", {"count": 5, "element_width": 7, "element_height": 8})
        self.assertEqual(curve.status_code, 200, curve.text)
        self.assertEqual(len(curve.json()["proposed_document"]["document"]["elements"]), 5)

    def test_bad_manual_parameters_and_stale_revision_rejected(self):
        self.assertEqual(self.prepare("grid", {"rows": 0}).status_code, 422)
        self.assertEqual(self.prepare("radial", {"radius": -1}).status_code, 422)
        response = self.client.post("/api/v1/prepare-pattern", json={
            "document": self.document, "document_revision": 99, "family": "grid"})
        self.assertEqual(response.status_code, 409)

    def test_free_keeps_original_positions(self):
        prepared = self.prepare("free")
        self.assertEqual(prepared.status_code, 200, prepared.text)
        result = prepared.json()
        self.assertEqual(result["mode"], "direct")
        actual = [(item["x"], item["y"]) for item in result["proposed_document"]["document"]["elements"]]
        expected = [(item["x"], item["y"]) for item in self.document["document"]["elements"]]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
