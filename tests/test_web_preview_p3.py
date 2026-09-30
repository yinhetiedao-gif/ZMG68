"""P3 preview is a read-only serialization of the same validated mesh as STL."""
from __future__ import annotations

import io
import json
from pathlib import Path
import unittest

import numpy as np
import trimesh
from fastapi.testclient import TestClient

from ppg.foundation import PatternDocument
from tests.test_manufacturing_backend_gate_v import geometry, polygon
from tests.test_web_server_wm3 import build_payload
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.manufacturing_backend import TrimeshBackend
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web.preview_artifact import export_preview_glb
from xiaomang_pattern_lab.web import create_app


class PreviewArtifactTests(unittest.TestCase):
    def test_hole_is_open_in_glb_and_stl_and_original_mesh_is_unchanged(self):
        source = geometry(polygon(
            "plate", ((0, 0), (20, 0), (20, 20), (0, 20)),
            holes=(((6, 6), (14, 6), (14, 14), (6, 14)),),
        ))
        result = TrimeshBackend().extrude(source, 2.0)
        original_vertices = result.mesh.vertices.copy()
        original_faces = result.mesh.faces.copy()
        stl_before = STLExporter().export_bytes(result)
        glb = export_preview_glb(result)
        stl_after = STLExporter().export_bytes(result)
        self.assertEqual(stl_before, stl_after)
        self.assertTrue(np.array_equal(result.mesh.vertices, original_vertices))
        self.assertTrue(np.array_equal(result.mesh.faces, original_faces))
        preview_mesh = trimesh.load(io.BytesIO(glb), file_type="glb", force="mesh")
        stl_mesh = trimesh.load(io.BytesIO(stl_before), file_type="stl", force="mesh")
        self.assertEqual(tuple(preview_mesh.extents), (20.0, 20.0, 2.0))
        self.assertEqual(tuple(stl_mesh.extents), (20.0, 20.0, 2.0))
        for mesh in (preview_mesh, stl_mesh):
            for face in mesh.faces:
                vertices = mesh.vertices[face]
                if np.allclose(vertices[:, 2], 2.0):
                    x, y = vertices[:, :2].mean(axis=0)
                    self.assertFalse(6.0 < x < 14.0 and 6.0 < y < 14.0)

    def test_multiple_components_are_not_unioned_or_moved_for_preview(self):
        source = geometry(
            polygon("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
            polygon("right", ((20, 0), (25, 0), (25, 5), (20, 5))),
        )
        result = TrimeshBackend().extrude(source, 2.0)
        preview = trimesh.load(io.BytesIO(export_preview_glb(result)), file_type="glb", force="mesh")
        self.assertEqual(result.component_count, 2)
        self.assertEqual(len(preview.faces), len(result.mesh.faces))
        self.assertTrue(np.allclose(np.sort(preview.vertices, axis=0), np.sort(result.mesh.vertices, axis=0)))
        self.assertEqual(tuple(preview.extents), (25.0, 5.0, 2.0))
        self.assertFalse(any(preview.vertices[face, 0].min() < 6 and preview.vertices[face, 0].max() > 19
                             for face in preview.faces))

    def test_hole_fixture_reaches_both_artifacts_through_one_http_result(self):
        fixture = Path(__file__).parent / "fixtures" / "p3_hole.pattern.json"
        document = PatternDocument.from_dict(json.loads(fixture.read_text(encoding="utf-8")))
        dto = PatternDocumentDTO.from_document(document, "hole-fixture", 0)
        with TestClient(create_app()) as client:
            build = client.post("/api/v1/manufacturing/build", json=build_payload(dto))
            self.assertEqual(build.status_code, 200, build.text)
            result_id = build.json()["manufacturing_result_id"]
            preview = client.get(f"/api/v1/manufacturing/{result_id}/preview.glb")
            stl = client.get(f"/api/v1/manufacturing/{result_id}/model.stl")
            self.assertEqual((preview.status_code, stl.status_code), (200, 200))
            self.assertEqual(build.json()["component_count"], 1)
            for mesh in (trimesh.load(io.BytesIO(preview.content), file_type="glb", force="mesh"),
                         trimesh.load(io.BytesIO(stl.content), file_type="stl", force="mesh")):
                self.assertEqual(tuple(mesh.extents), (20.0, 20.0, 2.0))
                for face in mesh.faces:
                    vertices = mesh.vertices[face]
                    if np.allclose(vertices[:, 2], 2.0):
                        x, y = vertices[:, :2].mean(axis=0)
                        self.assertFalse(6.0 < x < 14.0 and 6.0 < y < 14.0)


if __name__ == "__main__":
    unittest.main()
