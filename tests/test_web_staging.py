"""Temporary public staging changes only the HTTP boundary, not geometry."""
from __future__ import annotations

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.contracts import EvaluateRequestDTO, PatternDocumentDTO
from tests.test_web_server_wm3 import build_payload, circle_document
from xiaomang_pattern_lab.web import app as app_module


class WebStagingTests(unittest.TestCase):
    def test_staging_hides_api_docs_and_keeps_same_origin_contract(self):
        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/api/v1/health").status_code, 200)
                contract = client.get("/api/v1/contract").json()
                self.assertEqual((contract["schema_version"], contract["units"]), ("1.0", "mm"))
                self.assertEqual(client.get("/docs").status_code, 404)
                self.assertEqual(client.get("/openapi.json").status_code, 404)
                self.assertNotIn("access-control-allow-origin", client.get(
                    "/api/v1/health", headers={"Origin": "https://elsewhere.example"}).headers)

    def test_staging_limits_concurrent_expensive_builds(self):
        started = threading.Event()
        release = threading.Event()
        original_build = app_module._build

        def slow_build(*args):
            started.set()
            if not release.wait(10):
                raise AssertionError("test release timed out")
            return original_build(*args)

        dto = PatternDocumentDTO.from_document(circle_document(), "staging-test", 0)
        payload = build_payload(dto)
        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}), patch.object(
                app_module, "_build", side_effect=slow_build):
            with TestClient(create_app()) as client, ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(client.post, "/api/v1/manufacturing/build", json=payload)
                self.assertTrue(started.wait(5))
                try:
                    busy = client.post("/api/v1/manufacturing/build", json=payload)
                    self.assertEqual(busy.status_code, 429)
                    self.assertEqual(busy.json()["code"], "staging_busy")
                    # These are the same compute slot, not three independent UI tasks.
                    for endpoint in ("preview", "candidate", "fusion"):
                        conflict = client.post(f"/api/v1/fabric/{endpoint}", json={
                            "document": dto.to_dict(), "document_revision": dto.document_revision})
                        self.assertEqual(conflict.status_code, 429, endpoint)
                        self.assertEqual(conflict.json()["code"], "staging_busy")
                        self.assertIn("另一项", conflict.json()["message"])
                    self.assertEqual(client.get("/api/v1/health").status_code, 200)
                    # Opening/evaluating B is independent of A's 3D slot.
                    other = PatternDocumentDTO.from_document(circle_document(), "staging-b", 1)
                    evaluated = client.post("/api/v1/evaluate", json=EvaluateRequestDTO(other).to_dict())
                    self.assertEqual(evaluated.status_code, 200, evaluated.text)
                    self.assertEqual(evaluated.json()["document_id"], "staging-b")
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=20).status_code, 200)
                second = client.post("/api/v1/manufacturing/build", json=build_payload(other))
                self.assertEqual(second.status_code, 200, second.text)
                self.assertEqual(second.json()["document_id"], "staging-b")

    def test_each_compute_route_releases_slot_after_controlled_exception(self):
        for route, target in (("manufacturing/build", "_build"),
                              ("fabric/preview", "build_fabric_preview"),
                              ("fabric/candidate", "build_fabric_design"),
                              ("fabric/fusion", "build_fabric_design")):
            with self.subTest(route=route), patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}):
                dto = PatternDocumentDTO.from_document(circle_document(), "failed-a", 0)
                body = build_payload(dto) if route == "manufacturing/build" else {
                    "document": dto.to_dict(), "document_revision": 0}
                started, release = threading.Event(), threading.Event()

                def fail(*args, **kwargs):
                    started.set()
                    if not release.wait(10):
                        raise AssertionError("test release timed out")
                    raise RuntimeError("controlled computation failure")

                with TestClient(create_app(), raise_server_exceptions=False) as client:
                    with patch.object(app_module, target, side_effect=fail), ThreadPoolExecutor(max_workers=1) as pool:
                        first = pool.submit(client.post, "/api/v1/" + route, json=body)
                        self.assertTrue(started.wait(5))
                        try:
                            busy = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
                            self.assertEqual(busy.status_code, 429)
                            self.assertEqual(busy.json()["code"], "staging_busy")
                        finally:
                            release.set()
                        self.assertEqual(first.result(timeout=20).status_code, 500)
                    # Real B manufacture, not a cached response or a fake mesh.
                    other = PatternDocumentDTO.from_document(circle_document(), "after-failure-b", 1)
                    second = client.post("/api/v1/manufacturing/build", json=build_payload(other))
                    self.assertEqual(second.status_code, 200, second.text)
                    self.assertEqual(second.json()["document_id"], "after-failure-b")


if __name__ == "__main__":
    unittest.main()
