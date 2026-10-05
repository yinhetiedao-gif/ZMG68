"""WM3 HTTP boundary tests; no browser, database, or Tk application."""
from __future__ import annotations

import io
import math
import numpy as np
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import trimesh

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from tests.test_manufacturing_service_wm1 import printed_pattern_document
from xiaomang_pattern_lab.contracts import (
    EvaluateRequestDTO, ManufacturingBuildRequestDTO, PatternDocumentDTO,
)
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app
from xiaomang_pattern_lab.web.assets import InMemoryAssetResolver
from xiaomang_pattern_lab.web.runtime_store import (
    InMemoryManufacturingResultStore, StoredManufacturingResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def circle_document() -> PatternDocument:
    return PatternDocument(Canvas(100, 100, "mm", 1.0), Reference("", False),
                           [CircleElement("circle-1", 25, 25, 10, 10)])


def build_payload(dto: PatternDocumentDTO, height: float = 2.0) -> dict:
    value = ManufacturingBuildRequestDTO(dto.document_id, dto.document_revision, height).to_dict()
    value["document"] = dto.to_dict()
    return value


class WebServerWM3Tests(unittest.TestCase):
    def test_health_contract_openapi_and_cors(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/v1/health").json(),
                             {"status": "ok", "contract_version": "1.0",
                              "backend_commit": "UNKNOWN", "environment": "development",
                              "capabilities": {"fabric_preflight": True,
                                  "fabric_final_mesh": True, "fabric_stl_test_export": False}})
            self.assertEqual(client.get("/api/v1/contract").json()["units"], "mm")
            self.assertEqual(client.get("/docs").status_code, 200)
            paths = client.get("/openapi.json").json()["paths"]
            self.assertIn("application/json", paths["/api/v1/evaluate"]["post"]["requestBody"]["content"])
            allowed = client.options("/api/v1/evaluate", headers={
                "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            })
            self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173")
            denied = client.options("/api/v1/evaluate", headers={
                "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
            })
            self.assertNotIn("access-control-allow-origin", denied.headers)

    def test_evaluate_returns_world_mm_and_revision(self):
        dto = PatternDocumentDTO.from_document(circle_document(), "doc-1", 7)
        with TestClient(create_app()) as client:
            start = perf_counter()
            result = client.post("/api/v1/evaluate", json=EvaluateRequestDTO(dto).to_dict())
            print("WM3 evaluate latency ms:", round((perf_counter() - start) * 1000, 2))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["document_revision"], 7)
        self.assertEqual(result.json()["geometry"][0]["id"], "circle-1")
        self.assertEqual(result.json()["geometry"][0]["units"], "mm")
        self.assertEqual(result.json()["bounds_mm"]["width"], 10)

    def test_invalid_version_document_number_and_body_limit_are_controlled(self):
        dto = PatternDocumentDTO.from_document(circle_document(), "doc-1", 0)
        with TestClient(create_app()) as client:
            payload = EvaluateRequestDTO(dto).to_dict()
            payload["schema_version"] = "9.0"
            self.assertEqual(client.post("/api/v1/evaluate", json=payload).json()["code"],
                             "invalid_schema_version")
            self.assertEqual(client.post("/api/v1/evaluate", json={"schema_version": "1.0"}).status_code, 422)
            self.assertEqual(client.post("/api/v1/evaluate", data=b'{"value": NaN}').json()["code"],
                             "invalid_number")
            large = client.post("/api/v1/evaluate", content=b"x" * (2 * 1024 * 1024 + 1))
            self.assertEqual(large.status_code, 413)
            self.assertEqual(large.json()["code"], "request_too_large")

    def test_asset_must_be_server_registered_no_client_path_fallback(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "reference.png"
            source.write_bytes(b"test")
            doc = circle_document()
            doc.reference.source_path = str(source)
            dto = PatternDocumentDTO.from_document(doc, "doc-image", 0,
                                                    asset_bindings={str(source): "asset-1"})
            request = EvaluateRequestDTO(dto).to_dict()
            with TestClient(create_app()) as client:
                failure = client.post("/api/v1/evaluate", json=request)
            self.assertEqual(failure.status_code, 422)
            self.assertEqual(failure.json()["code"], "unresolved_asset")
            self.assertNotIn(str(source), failure.text)
            with TestClient(create_app(asset_resolver=InMemoryAssetResolver({"asset-1": str(source)}))) as client:
                success = client.post("/api/v1/evaluate", json=request)
            self.assertEqual(success.status_code, 200, success.text)
            self.assertNotIn(str(source), success.text)

    def test_build_download_and_stl_reload_reuse_one_result(self):
        dto = PatternDocumentDTO.from_document(circle_document(), "doc-stl", 4)
        with TestClient(create_app()) as client:
            start = perf_counter()
            build = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            print("WM3 circle build latency ms:", round((perf_counter() - start) * 1000, 2))
            self.assertEqual(build.status_code, 200, build.text)
            body = build.json()
            result_id = body["manufacturing_result_id"]
            self.assertEqual(body["status"], "completed")
            self.assertEqual(body["document_revision"], 4)
            self.assertEqual(body["component_count"], 1)
            self.assertEqual(body["bounds_mm"]["size_z"], 2)
            start = perf_counter()
            stl = client.get("/api/v1/manufacturing/%s/model.stl" % result_id)
            print("WM3 STL response latency ms:", round((perf_counter() - start) * 1000, 2))
            self.assertEqual(stl.status_code, 200)
            self.assertEqual(stl.headers["content-type"], "model/stl")
            self.assertIn(".stl", stl.headers["content-disposition"])
            self.assertIsNone(body["artifacts"][0]["sha256"])
            self.assertIsNone(body["artifacts"][0]["byte_size"])
            self.assertEqual(stl.content, client.get("/api/v1/manufacturing/%s/model.stl" % result_id).content)
            preview = client.get("/api/v1/manufacturing/%s/preview.glb" % result_id)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.headers["content-type"], "model/gltf-binary")
            self.assertEqual(preview.content[:4], b"glTF")
            glb_mesh = trimesh.load(io.BytesIO(preview.content), file_type="glb", force="mesh")
            self.assertEqual(tuple(round(value, 5) for value in glb_mesh.extents), (10.0, 10.0, 2.0))
            self.assertEqual(client.get("/api/v1/manufacturing/missing/model.stl").status_code, 404)
            self.assertEqual(client.get("/api/v1/manufacturing/missing/preview.glb").status_code, 404)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.stl"
            path.write_bytes(stl.content)
            reloaded = STLExporter.reload_as_mesh_result(path)
            report = MeshValidator().validate(reloaded)
            self.assertTrue(report.is_valid and report.is_watertight)
            self.assertEqual(report.component_count, 1)
            self.assertTrue(math.isclose(reloaded.height_mm, 2.0, abs_tol=1e-5))

    def test_printed_pattern_api_preserves_manufacturing_dimensions(self):
        printed, _ = printed_pattern_document()
        dto = PatternDocumentDTO.from_document(printed, "printed", 1)
        store = InMemoryManufacturingResultStore()
        with TestClient(create_app(result_store=store)) as client:
            start = perf_counter()
            build = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            print("WM3 printed build latency ms:", round((perf_counter() - start) * 1000, 2))
            self.assertEqual(build.status_code, 200, build.text)
            body = build.json()
            self.assertEqual(body["component_count"], 3)
            bounds = body["bounds_mm"]
            self.assertAlmostEqual(bounds["size_x"], 57.216907, places=3)
            self.assertAlmostEqual(bounds["size_y"], 19.899187, places=3)
            self.assertAlmostEqual(bounds["size_z"], 2.0, places=6)
            self.assertTrue(body["mesh_validation_summary"]["is_watertight"])
            stl = client.get("/api/v1/manufacturing/%s/model.stl" % body["manufacturing_result_id"])
            self.assertEqual(stl.status_code, 200)
            preview = client.get("/api/v1/manufacturing/%s/preview.glb" % body["manufacturing_result_id"])
            self.assertEqual(preview.status_code, 200)
            glb_mesh = trimesh.load(io.BytesIO(preview.content), file_type="glb", force="mesh")
            original = store.get(body["manufacturing_result_id"]).result.mesh_result.mesh
            self.assertEqual(len(glb_mesh.faces), len(original.faces))
            self.assertTrue(np.allclose(np.sort(glb_mesh.vertices, axis=0), np.sort(original.vertices, axis=0)))
            self.assertAlmostEqual(glb_mesh.extents[0], 57.216907, places=3)
            self.assertAlmostEqual(glb_mesh.extents[1], 19.899187, places=3)
            self.assertAlmostEqual(glb_mesh.extents[2], 2.0, places=6)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "printed.stl"
            path.write_bytes(stl.content)
            reloaded = STLExporter.reload_as_mesh_result(path)
            report = MeshValidator().validate(reloaded)
            self.assertTrue(report.is_valid and report.is_watertight)
            self.assertEqual(report.component_count, 3)
            self.assertAlmostEqual(reloaded.bounds[1][0] - reloaded.bounds[0][0], 57.216907, places=3)

    def test_empty_design_reports_specific_manufacturing_error(self):
        document = circle_document()
        document.elements = []
        dto = PatternDocumentDTO.from_document(document, "empty-design", 0)
        with TestClient(create_app()) as client:
            response = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "manufacturing_validation_failed")
        self.assertIn("没有可制造的二维元素", response.json()["message"])

    def test_store_is_bounded_and_ttl_expires(self):
        store = InMemoryManufacturingResultStore(max_entries=2, ttl_seconds=30)
        item = StoredManufacturingResult(None, {}, b"stl")
        with patch("xiaomang_pattern_lab.web.runtime_store.monotonic", return_value=100):
            store.put("a", item)
            store.put("b", item)
            store.put("c", item)
            self.assertIsNone(store.get("a"))
            self.assertIsNotNone(store.get("c"))
        with patch("xiaomang_pattern_lab.web.runtime_store.monotonic", return_value=131):
            self.assertIsNone(store.get("b"))
            self.assertIsNone(store.get("c"))

    def test_fresh_process_web_import_has_no_tk_or_legacy(self):
        command = (
            "import sys; import xiaomang_pattern_lab.web.app; "
            "assert 'tkinter' not in sys.modules; "
            "assert 'ppg.xiaomang_pipeline' not in sys.modules; "
            "assert 'bpy' not in sys.modules; print('WM3_HEADLESS_OK')"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        completed = subprocess.run([sys.executable, "-c", command], cwd=PROJECT_ROOT,
                                   env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("WM3_HEADLESS_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
