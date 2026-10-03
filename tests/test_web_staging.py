"""Temporary public staging changes only the HTTP boundary, not geometry."""
from __future__ import annotations

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
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
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=20).status_code, 200)


if __name__ == "__main__":
    unittest.main()
