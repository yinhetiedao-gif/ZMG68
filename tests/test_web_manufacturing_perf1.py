"""PERF-1: one validated build, cached identical requests, lazy read-only artifacts."""
from __future__ import annotations

from dataclasses import replace
import io
import unittest
from unittest.mock import patch

import trimesh
from fastapi.testclient import TestClient

from tests.test_web_server_wm3 import build_payload, circle_document
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.runtime_store import InMemoryManufacturingResultStore
import xiaomang_pattern_lab.web.app as web_app


class ManufacturingPerformanceContractTests(unittest.TestCase):
    def test_identical_request_reuses_mesh_and_lazy_artifacts(self):
        store = InMemoryManufacturingResultStore()
        dto = PatternDocumentDTO.from_document(circle_document(), "perf-circle", 7)
        original_build = ManufacturingService.build
        original_stl = STLExporter.export_bytes
        original_glb = web_app.export_preview_glb
        with patch.object(ManufacturingService, "build", autospec=True,
                          side_effect=lambda self, *args: original_build(self, *args)) as build_spy, \
             patch.object(STLExporter, "export_bytes", autospec=True,
                          side_effect=lambda self, *args: original_stl(self, *args)) as stl_spy, \
             patch.object(web_app, "export_preview_glb", side_effect=original_glb) as glb_spy, \
             TestClient(create_app(result_store=store)) as client:
            first = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(first.status_code, 200, first.text)
            result_id = first.json()["manufacturing_result_id"]
            stored = store.get(result_id)
            self.assertIsNotNone(stored)
            self.assertIsNone(stored.stl_bytes)
            self.assertIsNone(stored.preview_glb_bytes)
            self.assertIsNone(first.json()["artifacts"][0]["byte_size"])
            self.assertIsNone(first.json()["artifacts"][0]["sha256"])
            self.assertEqual((build_spy.call_count, stl_spy.call_count, glb_spy.call_count), (1, 0, 0))

            second = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.json(), first.json())
            self.assertEqual(build_spy.call_count, 1)

            stl_a = client.get(f"/api/v1/manufacturing/{result_id}/model.stl")
            stl_b = client.get(f"/api/v1/manufacturing/{result_id}/model.stl")
            preview_a = client.get(f"/api/v1/manufacturing/{result_id}/preview.glb")
            preview_b = client.get(f"/api/v1/manufacturing/{result_id}/preview.glb")
            self.assertEqual((stl_a.status_code, preview_a.status_code), (200, 200))
            self.assertEqual(stl_a.content, stl_b.content)
            self.assertEqual(preview_a.content, preview_b.content)
            self.assertEqual((build_spy.call_count, stl_spy.call_count, glb_spy.call_count), (1, 1, 1))
            self.assertEqual(tuple(trimesh.load(io.BytesIO(preview_a.content), file_type="glb", force="mesh").extents),
                             (10.0, 10.0, 2.0))
            self.assertEqual(tuple(trimesh.load(io.BytesIO(stl_a.content), file_type="stl", force="mesh").extents),
                             (10.0, 10.0, 2.0))

            changed_height = client.post("/api/v1/manufacturing/build", json=build_payload(dto, height=3))
            changed_revision = client.post("/api/v1/manufacturing/build",
                                           json=build_payload(replace(dto, document_revision=8)))
            self.assertEqual((changed_height.status_code, changed_revision.status_code), (200, 200))
            self.assertEqual(build_spy.call_count, 3)
            self.assertNotEqual(changed_height.json()["manufacturing_result_id"], result_id)
            self.assertNotEqual(changed_revision.json()["manufacturing_result_id"], result_id)

    def test_expired_result_is_not_reused(self):
        store = InMemoryManufacturingResultStore(ttl_seconds=0.001)
        dto = PatternDocumentDTO.from_document(circle_document(), "perf-expiry", 0)
        with TestClient(create_app(result_store=store)) as client:
            first = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(first.status_code, 200)
            result_id = first.json()["manufacturing_result_id"]
            store.delete(result_id)
            self.assertIsNone(store.get(result_id))
            again = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(again.status_code, 200)
            self.assertEqual(again.json()["manufacturing_result_id"], result_id)


if __name__ == "__main__":
    unittest.main()
