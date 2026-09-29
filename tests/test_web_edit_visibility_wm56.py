"""WM5.6: real import → edited DTO → Evaluate retains renderable IDs and bounds."""
from __future__ import annotations

from copy import deepcopy
import unittest

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.fixtures import build_fixed_suite
from xiaomang_pattern_lab.web import create_app


class WebEditVisibilityWM56Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = build_fixed_suite()

    def test_png_and_imported_star_edits_keep_final_geometry(self):
        with TestClient(create_app()) as client:
            for name in ("regular_dot_matrix", "star_halftone"):
                with self.subTest(name=name):
                    response = client.post("/api/v1/assets", content=self.fixtures[name].read_bytes(),
                                           headers={"Content-Type": "image/png", "X-Filename": name + ".png"})
                    self.assertEqual(response.status_code, 200, response.text)
                    imported = client.post("/api/v1/import", json={"asset_id": response.json()["asset_id"]})
                    self.assertEqual(imported.status_code, 200, imported.text)
                    dto = imported.json()
                    source = dto["document"]["elements"][0]
                    before = self.evaluate(client, dto)
                    first = next(item for item in before["geometry"] if item["id"] == source["id"])
                    self.assertGreater(len(before["geometry"]), 0)
                    self.assertGreater(first["width"], 0)
                    self.assertGreater(first["height"], 0)
                    for key, delta in (("x", 2), ("y", 2), ("width", 1), ("height", 1), ("rotation", 15)):
                        changed = deepcopy(dto)
                        changed["document_revision"] = 1
                        changed["document"]["elements"][0][key] += delta
                        after = self.evaluate(client, changed)
                        self.assertEqual(len(after["geometry"]), len(before["geometry"]))
                        edited = next(item for item in after["geometry"] if item["id"] == source["id"])
                        self.assertGreater(edited["width"], 0)
                        self.assertGreater(edited["height"], 0)
                        self.assertGreater(after["bounds_mm"]["width"], 0)
                        self.assertEqual(edited["id"], first["id"])

    @staticmethod
    def evaluate(client: TestClient, dto: dict):
        response = client.post("/api/v1/evaluate", json={"schema_version": "1.0",
            "document_id": dto["document_id"], "document_revision": dto["document_revision"],
            "document": dto})
        assert response.status_code == 200, response.text
        return response.json()
