"""Built-in documents must remain ordinary PatternDocument projects."""
import json
from pathlib import Path
import struct
import unittest
from copy import deepcopy

from fastapi.testclient import TestClient

from ppg.foundation import FoundationPipeline, PatternDocument
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.web import create_app


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "web" / "src" / "examples" / "fixtures"


class BuiltInExamplesTests(unittest.TestCase):
    def _document(self, name: str) -> PatternDocument:
        payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["canvas"]["unit"], "mm")
        self.assertEqual(payload["canvas"]["mm_per_unit"], 1)
        return PatternDocument.from_dict(payload)

    def test_basic_grid_evaluates_and_exports_standard_stl(self):
        document = self._document("basic-grid.pattern.json")
        geometry = evaluate_pattern_document(document)
        self.assertEqual(len(geometry), 9)
        self.assertTrue(all(item.type == "circle" for item in geometry))
        self._manufactures(document)

    def test_gradient_evaluates_size_rotation_and_exports_standard_stl(self):
        document = self._document("gradient-grid.pattern.json")
        geometry = evaluate_pattern_document(document)
        self.assertEqual(len(geometry), 16)
        self.assertLess(geometry[0].width, geometry[3].width)
        self.assertLess(geometry[0].rotation, geometry[3].rotation)
        self.assertTrue(all(item.type == "rect" for item in geometry))
        self._manufactures(document)

    def test_web_example_load_grid_edit_and_reset_use_ordinary_manufacturing(self):
        for name in ("basic-grid.pattern.json", "gradient-grid.pattern.json"):
            with self.subTest(example=name), TestClient(create_app()) as client:
                original = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
                self.assertEqual(PatternDocument.from_dict(original).to_dict(), original)
                variants = [(0, original), (2, deepcopy(original))]
                if name == "basic-grid.pattern.json":
                    edited = deepcopy(original)
                    edited["metadata"]["xiaomang_pattern_lab.parametric"]["grid"]["rows"] = 4
                    variants.insert(1, (1, edited))
                for revision, payload in variants:
                    with self.subTest(revision=revision):
                        identity = "browser-" + name
                        dto = {"schema_version": "1.0", "document_id": identity,
                               "document_revision": revision, "document": payload, "assets": []}
                        body = {"schema_version": "1.0", "document_id": identity,
                                "document_revision": revision, "height_mm": 2.0, "document": dto}
                        built = client.post("/api/v1/manufacturing/build", json=body)
                        self.assertEqual(built.status_code, 200, built.text)
                        result = built.json()
                        self.assertEqual(result["document_id"], identity)
                        self.assertEqual(result["document_revision"], revision)
                        exported = client.get("/api/v1/manufacturing/%s/model.stl" % result["manufacturing_result_id"])
                        self.assertEqual(exported.status_code, 200, exported.text)
                        self.assertGreater(len(exported.content), 84)

    def test_real_60_by_60_mm_document_matches_manufacturing_and_stl(self):
        payload = json.loads((FIXTURES / "basic-grid.pattern.json").read_text(encoding="utf-8"))
        payload["canvas"]["mm_per_unit"] = 1.5  # The existing 40 × 40 world-unit result becomes 60 × 60 mm.
        payload["metadata"]["web_real_size_confirmation"] = {
            "width_mm": 60.0, "height_mm": 60.0, "mm_per_unit": 1.5,
        }
        self.assertEqual(PatternDocument.from_dict(payload).to_dict(), payload)
        with TestClient(create_app()) as client:
            dto = {"schema_version": "1.0", "document_id": "confirmed-60mm",
                   "document_revision": 1, "document": payload, "assets": []}
            body = {"schema_version": "1.0", "document_id": dto["document_id"],
                    "document_revision": 1, "height_mm": 2.0, "document": dto}
            built = client.post("/api/v1/manufacturing/build", json=body)
            self.assertEqual(built.status_code, 200, built.text)
            result = built.json()
            self.assertAlmostEqual(result["bounds_mm"]["size_x"], 60, places=5)
            self.assertAlmostEqual(result["bounds_mm"]["size_y"], 60, places=5)
            self.assertAlmostEqual(result["bounds_mm"]["size_z"], 2, places=5)
            exported = client.get("/api/v1/manufacturing/%s/model.stl" % result["manufacturing_result_id"])
            self.assertEqual(exported.status_code, 200, exported.text)
            raw = exported.content
            count = struct.unpack_from("<I", raw, 80)[0]
            coordinates = [struct.unpack_from("<fff", raw, 84 + face * 50 + 12 + vertex * 12)
                           for face in range(count) for vertex in range(3)]
            for axis, expected in enumerate((60.0, 60.0, 2.0)):
                extent = max(point[axis] for point in coordinates) - min(point[axis] for point in coordinates)
                self.assertAlmostEqual(extent, expected, places=4)

    def _manufactures(self, document: PatternDocument):
        before = document.to_dict()
        session = PatternLabSession(FoundationPipeline(None, None), ROOT / "work", document=document)
        result = ManufacturingService().build(session, 2.0)
        self.assertTrue(result.ready)
        self.assertTrue(result.mesh_report.is_watertight)
        binary = STLExporter().export_bytes(result.mesh_result)
        face_count = struct.unpack_from("<I", binary, 80)[0]
        self.assertGreater(face_count, 0)
        self.assertEqual(len(binary), 84 + 50 * face_count)
        self.assertEqual(document.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
