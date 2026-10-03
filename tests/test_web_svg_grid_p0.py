"""P0-A: original 60 mm nine-circle SVGs, with and without a white background."""
from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.web import create_app


FIXTURES = Path(__file__).parent / "fixtures"


class WebSVGGridP0Tests(unittest.TestCase):
    def test_original_svg_import_analyze_prepare_and_apply_grid(self):
        with TestClient(create_app()) as client:
            for name in ("qa_grid_no_background.svg", "qa_grid_white_background.svg"):
                with self.subTest(fixture=name):
                    upload = client.post("/api/v1/assets", content=(FIXTURES / name).read_bytes(),
                        headers={"Content-Type": "image/svg+xml", "X-Filename": name})
                    self.assertEqual(upload.status_code, 200, upload.text)
                    imported = client.post("/api/v1/import", json={"asset_id": upload.json()["asset_id"]})
                    self.assertEqual(imported.status_code, 200, imported.text)
                    dto = imported.json()
                    self.assertEqual(len(dto["document"]["elements"]), 10 if "white" in name else 9)
                    self.assertEqual(sum(item["type"] == "circle" for item in dto["document"]["elements"]), 9)
                    self.assertEqual(len(dto["document"]["groups"]), 1)
                    body = {"document": dto, "document_revision": dto["document_revision"]}
                    analysis = client.post("/api/v1/analyze-pattern", json=body)
                    self.assertEqual(analysis.status_code, 200, analysis.text)
                    self.assertEqual(analysis.json()["recommended_family"], "grid")
                    # The Web layout selector submits an empty parameter map,
                    # which requests editable manual defaults rather than direct apply.
                    prepared = client.post("/api/v1/prepare-pattern", json={
                        **body, "family": "grid", "parameters": {}})
                    self.assertEqual(prepared.status_code, 200, prepared.text)
                    self.assertEqual(prepared.json()["mode"], "manual")
                    proposal = prepared.json()["proposed_document"]
                    self.assertEqual(len(proposal["document"]["metadata"]["xiaomang_pattern_lab.parametric"]
                        ["source_elements"]), len(dto["document"]["elements"]))
                    final_ids = {item["id"] for item in proposal["document"]["elements"]}
                    self.assertTrue(all(set(group["element_ids"]) <= final_ids
                        for group in proposal["document"]["groups"]))
                    evaluated = client.post("/api/v1/evaluate", json={
                        "schema_version": "1.0", "document_id": proposal["document_id"],
                        "document_revision": proposal["document_revision"], "document": proposal})
                    self.assertEqual(evaluated.status_code, 200, evaluated.text)
                    self.assertEqual(len(evaluated.json()["geometry"]), 9)
                    edited = client.post("/api/v1/prepare-pattern", json={
                        **body, "family": "grid", "parameters": {"rows": 3, "columns": 3,
                            "spacing_x": 16, "spacing_y": 16}})
                    self.assertEqual(edited.status_code, 200, edited.text)
                    self.assertEqual(edited.json()["mode"], "manual")
                    self.assertEqual(len(edited.json()["preview"]["geometry"]), 9)
                    direct = client.post("/api/v1/apply-pattern", json={**body, "family": "grid"})
                    self.assertEqual(direct.status_code, 200, direct.text)
                    self.assertEqual(len(direct.json()["document"]["elements"]), 9)


if __name__ == "__main__":
    unittest.main()
