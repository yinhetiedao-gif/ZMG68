"""Built-in documents must remain ordinary PatternDocument projects."""
import json
from pathlib import Path
import struct
import unittest

from ppg.foundation import FoundationPipeline, PatternDocument
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter


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
