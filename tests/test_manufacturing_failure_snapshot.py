"""Dev-only evidence capture; manufacturing validation itself is unchanged."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.test_web_server_wm3 import build_payload, circle_document
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.mesh_validation import MeshValidationIssue, MeshValidator
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.web import create_app


class ManufacturingFailureSnapshotTests(unittest.TestCase):
    def test_disabled_by_default_even_for_validation_failure(self):
        document = circle_document()
        document.elements = []
        dto = PatternDocumentDTO.from_document(document, "empty", 2)
        with TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS", None)
            directory = Path(temporary) / "failures"
            with TestClient(create_app(failure_snapshot_dir=directory)) as client:
                response = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["code"], "manufacturing_validation_failed")
            self.assertIsNone(response.json()["details"])
            self.assertFalse(directory.exists())

    def test_enabled_captures_reproducible_gate_t_failure_without_secrets(self):
        document = circle_document()
        document.elements = []
        document.metadata["api_key"] = "never-record-this-secret"
        dto = PatternDocumentDTO.from_document(document, "empty", 7)
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS": "1"}
        ):
            directory = Path(temporary) / "failures"
            with self.assertLogs("xiaomang_pattern_lab.web.app", level="INFO") as logs:
                with TestClient(create_app(failure_snapshot_dir=directory)) as client:
                    responses = [client.post("/api/v1/manufacturing/build", json=build_payload(dto, 2.0))
                                 for _ in range(2)]
            self.assertTrue(all(response.status_code == 422 for response in responses))
            failure_ids = [response.json()["details"]["failure_id"] for response in responses]
            self.assertEqual(len(set(failure_ids)), 2)
            for failure_id in failure_ids:
                self.assertIn("failure_id=" + failure_id, "\n".join(logs.output))
            files = sorted(directory.glob("*.json"))
            self.assertEqual(len(files), 2)
            self.assertNotEqual(files[0].name, files[1].name)
            self.assertEqual({path.stem for path in files}, set(failure_ids))
            snapshot = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(snapshot["failure_id"], files[0].stem)
            self.assertEqual(snapshot["document_id"], "empty")
            self.assertEqual(snapshot["document_revision"], 7)
            self.assertEqual(snapshot["height_mm"], 2.0)
            self.assertEqual(snapshot["pattern_document_dto"]["document"]["elements"], [])
            self.assertEqual(snapshot["error_code"], "manufacturing_validation_failed")
            self.assertIn("geometry", snapshot["validation_summary"])
            self.assertIn("conversion", snapshot["validation_summary"])
            self.assertIn("timestamp_utc", snapshot)
            self.assertEqual(snapshot["pattern_document_dto"]["document"]["metadata"]["api_key"],
                             "[REDACTED]")
            self.assertNotIn("never-record-this-secret", files[0].read_text(encoding="utf-8"))
            self.assertNotIn(str(directory), files[0].read_text(encoding="utf-8"))

    def test_gate_w_degenerate_summary_is_saved_and_original_error_preserved(self):
        dto = PatternDocumentDTO.from_document(circle_document(), "degenerate", 3)

        def simulated_bad_report(mesh):
            report = MeshValidator().validate(mesh)
            issue = MeshValidationIssue("degenerate_faces", "error", "Mesh 存在退化三角面。",
                                        metadata={"degenerate_face_count": 1, "epsilon_mm2": 1e-12})
            return replace(report, degenerate_face_count=1, error_count=1,
                           issues=report.issues + (issue,))

        with TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS": "1"}
        ), patch.object(PatternLabSession, "validate_manufacturing_mesh", side_effect=simulated_bad_report):
            directory = Path(temporary)
            with TestClient(create_app(failure_snapshot_dir=directory)) as client:
                response = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["code"], "manufacturing_validation_failed")
            snapshot = json.loads(next(directory.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(response.json()["details"]["failure_id"], snapshot["failure_id"])
            self.assertEqual(snapshot["validation_summary"]["mesh"]["degenerate_face_count"], 1)
            self.assertEqual(snapshot["document_revision"], 3)

    def test_snapshot_io_failure_does_not_hide_manufacturing_error(self):
        document = circle_document()
        document.elements = []
        dto = PatternDocumentDTO.from_document(document, "empty", 0)
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS": "1"}
        ), patch("xiaomang_pattern_lab.web.app.save_manufacturing_failure",
                 side_effect=PermissionError("denied")):
            with TestClient(create_app(failure_snapshot_dir=Path(temporary))) as client:
                response = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "manufacturing_validation_failed")
        self.assertIsNone(response.json()["details"])


if __name__ == "__main__":
    unittest.main()
