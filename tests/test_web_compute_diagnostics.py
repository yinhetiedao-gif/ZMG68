"""Controlled task-slot logs; real HTTP routes, no Render traffic/restarts."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_fusion import FabricFusionFailure
from xiaomang_pattern_lab.web import app as app_module, create_app
from xiaomang_pattern_lab.web.compute_diagnostics import ComputeDiagnostics
from tests.test_web_server_wm3 import build_payload, circle_document
from tests.test_fabric_original_shape import fixture


def events(capture):
    return [json.loads(record.getMessage().split("compute_task ", 1)[1])
            for record in capture.records if record.getMessage().startswith("compute_task ")]


class ComputeDiagnosticTests(unittest.TestCase):
    def assert_lifecycle(self, logs, outcome="completed"):
        start = next(log for log in logs if log["event"] == "start")
        group = [log for log in logs if log["task_id"] == start["task_id"]]
        self.assertEqual([log["event"] for log in group if log["event"] != "stage"],
                         ["start", "end", "released"])
        self.assertEqual(next(log for log in group if log["event"] == "end")["outcome"], outcome)
        self.assertTrue(all(log["request_id"] == start["request_id"] for log in group))
        self.assertTrue(all(log["pid"] == os.getpid() for log in group))
        self.assertEqual([log["elapsed_ms"] for log in group], sorted(log["elapsed_ms"] for log in group))
        self.assertIn("+00:00", start["started_at"])
        self.assertTrue(all("+00:00" in log["recorded_at"] for log in group))
        return group

    def test_busy_records_actual_owner_until_completion_then_second_work_succeeds(self):
        started, release = threading.Event(), threading.Event()
        original = app_module._build
        a = PatternDocumentDTO.from_document(circle_document(), "private-work-a", 2)
        b = PatternDocumentDTO.from_document(circle_document(), "private-work-b", 3)
        a.document["metadata"]["private_probe"] = "private image content not for diagnostics"

        def slow(*args):
            started.set()
            if not release.wait(10):
                raise AssertionError("test release timed out")
            return original(*args)

        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}), self.assertLogs("uvicorn.error", level="INFO") as capture:
            with TestClient(create_app()) as client, ThreadPoolExecutor(max_workers=1) as pool:
                with patch.object(app_module, "_build", side_effect=slow):
                    pending = pool.submit(client.post, "/api/v1/manufacturing/build", json=build_payload(a))
                    self.assertTrue(started.wait(5))
                    try:
                        for endpoint in ("/api/v1/fabric/preview", "/api/v1/manufacturing/build"):
                            body = build_payload(b) if endpoint.endswith("build") else {"document": b.to_dict(), "document_revision": 3}
                            response = client.post(endpoint, json=body)
                            self.assertEqual(response.status_code, 429)
                            self.assertEqual(response.json()["code"], "staging_busy")
                        current = events(capture)
                        owner = next(log for log in current if log["event"] == "start")
                        self.assertNotIn("released", [log["event"] for log in current])
                        busy = [log for log in current if log["event"] == "busy"]
                        self.assertEqual(len(busy), 2)
                        for log in busy:
                            self.assertIsNone(log["task_id"])  # Rejected request never starts a task.
                            self.assertEqual(log["occupied"]["task_id"], owner["task_id"])
                            self.assertEqual(log["occupied"]["stage"], "standard_manufacture")
                            self.assertEqual(log["occupied"]["revision"], 2)
                            self.assertGreater(log["occupied"]["elapsed_ms"], 0)
                            self.assertNotEqual(log["request_id"], owner["request_id"])
                    finally:
                        release.set()
                    first = pending.result(timeout=20)
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(first.json()["document_id"], "private-work-a")
                second = client.post("/api/v1/manufacturing/build", json=build_payload(b))
                self.assertEqual(second.status_code, 200, second.text)
                self.assertEqual(second.json()["document_id"], "private-work-b")
                before_cache = len(events(capture))
                self.assertEqual(client.post("/api/v1/manufacturing/build", json=build_payload(b)).status_code, 200)
                self.assertEqual(len(events(capture)), before_cache)  # Cached results do not acquire the slot.
        logs = events(capture)
        self.assert_lifecycle(logs)
        starts = [log for log in logs if log["event"] == "start"]
        self.assertEqual(len(starts), 2)
        self.assert_lifecycle([log for log in logs if log["task_id"] == starts[1]["task_id"]])
        self.assertNotEqual(starts[0]["task_id"], starts[1]["task_id"])
        self.assertEqual(starts[0]["document_ref"], sha256(b"private-work-a").hexdigest()[:16])
        self.assertEqual(starts[1]["revision"], 3)
        self.assertNotIn("private-work", json.dumps(logs))
        self.assertNotIn("private image content", json.dumps(logs))
        self.assertNotIn("secret.png", json.dumps(logs))
        for record in capture.records:
            value = record.getMessage()
            if value.startswith("compute_task ") and json.loads(value.split("compute_task ", 1)[1])["event"] != "stage":
                print("LOCAL CAPTURE:", value)

    def test_all_four_routes_have_start_stage_end_release_and_authoritative_counts(self):
        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}), TestClient(create_app()) as client:
            for route in ("manufacturing/build", "fabric/preview", "fabric/candidate", "fabric/fusion"):
                with self.subTest(route=route), self.assertLogs("uvicorn.error", level="INFO") as capture:
                    document = circle_document() if route.endswith("build") else fixture(1)
                    dto = PatternDocumentDTO.from_document(document, route.replace("/", "-"), 1)
                    body = build_payload(dto) if route.endswith("build") else {"document": dto.to_dict(), "document_revision": 1}
                    result = client.post("/api/v1/" + route, json=body)
                    self.assertEqual(result.status_code, 200, result.text)
                group = self.assert_lifecycle(events(capture))
                self.assertEqual(group[0]["endpoint"], "/api/v1/" + route)
                self.assertEqual(group[0]["source_element_count"], 1)
                self.assertIsNone(group[0]["instance_count"])
                if route.startswith("fabric/"):
                    self.assertEqual(group[-1]["instance_count"], 1)

    def test_exceptions_are_logged_without_payload_or_paths_and_release_all_routes(self):
        for route, target, failure, status in (
            ("manufacturing/build", "_build", RuntimeError, 500),
            ("fabric/preview", "build_fabric_preview", ValueError, 422),
            ("fabric/candidate", "build_fabric_design", RuntimeError, 500),
            ("fabric/fusion", "build_fabric_design", RuntimeError, 500),
        ):
            with self.subTest(route=route), patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}):
                dto = PatternDocumentDTO.from_document(fixture(1), "failure-a", 1)
                body = build_payload(dto) if route.endswith("build") else {"document": dto.to_dict(), "document_revision": 1}
                with TestClient(create_app(), raise_server_exceptions=False) as client:
                    with self.assertLogs("uvicorn.error", level="INFO") as capture, patch.object(
                            app_module, target, side_effect=failure("/private/secret.png private payload")):
                        result = client.post("/api/v1/" + route, json=body)
                        self.assertEqual(result.status_code, status)
                    group = self.assert_lifecycle(events(capture), "error")
                    self.assertIsNotNone(group[-2]["error_type"])
                    self.assertNotIn("secret.png", json.dumps(events(capture)))
                    second = PatternDocumentDTO.from_document(circle_document(), "recover-b", 2)
                    self.assertEqual(client.post("/api/v1/manufacturing/build", json=build_payload(second)).status_code, 200)

    def test_legacy_base_only_optional_plan_is_not_changed_by_diagnostic_counting(self):
        document = fixture(1, mode="cells_with_base")
        document.metadata["fabric_config"].update(shape_source="unit_cell", unit_cell=None)
        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}), TestClient(create_app()) as client:
            for endpoint in ("preview", "candidate", "fusion"):
                with self.subTest(endpoint=endpoint), self.assertLogs("uvicorn.error", level="INFO") as capture:
                    dto = PatternDocumentDTO.from_document(document, "legacy-" + endpoint, 1)
                    response = client.post("/api/v1/fabric/" + endpoint, json={"document": dto.to_dict(), "document_revision": 1})
                    self.assertEqual(response.status_code, 200, response.text)
                group = self.assert_lifecycle(events(capture))
                self.assertEqual(group[-1]["instance_count"], 0)

    def test_handled_fusion_422_is_logged_as_error_not_success(self):
        dto = PatternDocumentDTO.from_document(fixture(1), "handled-failure", 1)
        with patch.dict(os.environ, {"XIAOMANG_STAGING": "1"}), TestClient(create_app()) as client:
            with self.assertLogs("uvicorn.error", level="INFO") as capture, patch.object(
                    app_module.FabricFusionService, "build", side_effect=FabricFusionFailure("mesh_validation", "invalid sample")):
                response = client.post("/api/v1/fabric/fusion", json={"document": dto.to_dict(), "document_revision": 1})
                self.assertEqual(response.status_code, 422)
            group = self.assert_lifecycle(events(capture), "error")
            self.assertEqual(group[-2]["stage"], "fusion_and_validation")
            self.assertEqual(group[-2]["error_type"], "FabricFusionFailure")
            b = PatternDocumentDTO.from_document(circle_document(), "recover-b", 1)
            self.assertEqual(client.post("/api/v1/manufacturing/build", json=build_payload(b)).status_code, 200)

    def test_logging_handler_failure_cannot_strand_or_release_running_work(self):
        slot = threading.BoundedSemaphore(1)
        diagnostics = ComputeDiagnostics(slot)
        dto = PatternDocumentDTO.from_document(circle_document(), "private", 1)
        with patch.object(diagnostics.logger, "info", side_effect=RuntimeError("log sink failed")):
            with self.assertRaises(ValueError):
                with diagnostics.task("/api/v1/manufacturing/build", dto) as task:
                    task.phase("standard_manufacture")
                    self.assertFalse(slot.acquire(blocking=False))
                    raise ValueError("compute failed")
            self.assertTrue(slot.acquire(blocking=False))
            slot.release()
            self.assertEqual(diagnostics.active, {})

    def test_development_mode_diagnostics_do_not_add_a_concurrency_limit(self):
        diagnostics = ComputeDiagnostics(None)
        dto = PatternDocumentDTO.from_document(circle_document(), "development", 1)
        with self.assertLogs("uvicorn.error", level="INFO") as capture:
            with diagnostics.task("/api/v1/fabric/preview", dto):
                with diagnostics.task("/api/v1/fabric/preview", dto):
                    self.assertEqual(len(diagnostics.active), 2)
        self.assertEqual(len([log for log in events(capture) if log["event"] == "start"]), 2)
        self.assertNotIn("busy", [log["event"] for log in events(capture)])


if __name__ == "__main__":
    unittest.main()
