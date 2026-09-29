"""WM5.5 real HTTP upload → existing Python conversion → editable DTO."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.fixtures import ROOT, build_fixed_suite
from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.assets import TemporaryAssetStore


class WebImportWM55Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = build_fixed_suite()

    def setUp(self):
        self.client = TestClient(create_app())

    def tearDown(self):
        self.client.close()

    def upload(self, data: bytes, media_type: str, filename: str):
        return self.client.post("/api/v1/assets", content=data, headers={
            "Content-Type": media_type, "X-Filename": filename,
        })

    def imported(self, uploaded):
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        identifier = uploaded.json()["asset_id"]
        response = self.client.post("/api/v1/import", json={"asset_id": identifier})
        self.assertEqual(response.status_code, 200, response.text)
        dto = response.json()
        self.assertEqual(dto["schema_version"], "1.0")
        self.assertGreater(len(dto["document"]["elements"]), 0)
        self.assertNotIn("source_path", str(dto["assets"]))
        self.assertNotIn("xiaomang-assets-", response.text)
        evaluated = self.client.post("/api/v1/evaluate", json={
            "schema_version": "1.0", "document_id": dto["document_id"],
            "document_revision": 0, "document": dto,
        })
        self.assertEqual(evaluated.status_code, 200, evaluated.text)
        self.assertGreater(len(evaluated.json()["geometry"]), 0)
        return dto, evaluated.json()

    def test_png_jpg_and_three_dot_patterns(self):
        for name in ("regular_dot_matrix", "size_gradient_dot_matrix", "star_halftone"):
            with self.subTest(name=name):
                data = self.fixtures[name].read_bytes()
                dto, _ = self.imported(self.upload(data, "image/png", name + ".png"))
                self.assertTrue(all(item["type"] != "bitmap" for item in dto["document"]["elements"]))
        self.imported(self.upload((ROOT / "regular_dot_matrix.jpg").read_bytes(),
                                  "image/jpeg", "regular_dot_matrix.jpg"))

    def test_svg_with_hole_and_editable_shapes(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path id="ring" fill="black" fill-rule="evenodd" d="M 0 0 H 100 V 100 H 0 Z M 25 25 H 75 V 75 H 25 Z"/><circle id="dot" cx="50" cy="50" r="5" fill="black"/></svg>'
        dto, evaluated = self.imported(self.upload(svg, "image/svg+xml", "hole.svg"))
        self.assertIn("ring", [item["id"] for item in dto["document"]["elements"]])
        ring = next(item for item in evaluated["geometry"] if item["id"] == "ring")
        self.assertEqual(ring["style"]["fill-rule"], "evenodd")

    def test_rejects_invalid_oversized_missing_and_expired(self):
        self.assertEqual(self.upload(b"nonsense", "text/plain", "x.txt").status_code, 422)
        self.assertEqual(self.upload(b"<svg><!DOCTYPE x></svg>", "image/svg+xml", "bad.svg").status_code, 422)
        self.assertEqual(self.upload(b"x" * (8 * 1024 * 1024 + 1), "image/png", "large.png").status_code, 413)
        self.assertEqual(self.client.post("/api/v1/import", json={"asset_id": "missing"}).status_code, 404)
        uploaded = self.upload(self.fixtures["regular_dot_matrix"].read_bytes(), "image/png", "valid.png")
        with patch("xiaomang_pattern_lab.web.app._import_asset", side_effect=RuntimeError("C:\\private\\image.png")):
            failed = self.client.post("/api/v1/import", json={"asset_id": uploaded.json()["asset_id"]})
        self.assertEqual(failed.status_code, 422)
        self.assertNotIn("C:\\private", failed.text)
        store = TemporaryAssetStore(ttl_seconds=0)
        with TestClient(create_app(asset_store=store)) as client:
            result = client.post("/api/v1/assets", content=self.fixtures["regular_dot_matrix"].read_bytes(),
                                 headers={"Content-Type": "image/png"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(client.post("/api/v1/import", json={
                "asset_id": result.json()["asset_id"],
            }).status_code, 404)


if __name__ == "__main__":
    unittest.main()
