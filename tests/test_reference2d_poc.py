from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json
import os
import subprocess
import sys

from reference2d_poc.models import Document2D
from reference2d_poc.poc_runner import FIXTURE_DOTS, create_dot_halftone_fixture
from reference2d_poc.reference2d_service import Reference2DService
from reference2d_poc.svg_parser import SVGParser
from reference2d_poc.primitive_recognizer import PrimitiveRecognizer


class Reference2DPOCTests(unittest.TestCase):
    def test_stage_a_raster_to_editable_geometry_roundtrip(self) -> None:
        """验收：隐藏原图后可编辑，保存/恢复不需要再次分析 PNG。"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = create_dot_halftone_fixture(root / "input.png")
            result = Reference2DService().reconstruct(source, root / "trace.svg")
            document = result.document

            self.assertGreaterEqual(len(result.svg.paths), len(FIXTURE_DOTS))
            self.assertGreaterEqual(len(document.geometry_layer.dots), len(FIXTURE_DOTS))
            self.assertEqual(result.report()["rejected_count"], 0)
            self.assertTrue(document.reference_layer.visible)
            document.hide_reference()
            self.assertFalse(document.reference_layer.visible)
            self.assertEqual(len(document.geometry_layer.dots), len(FIXTURE_DOTS))

            dot = document.geometry_layer.dots[0]
            selected = document.select_at(dot.x, dot.y)
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, dot.id)
            old_radius, old_position = dot.radius_x, (dot.x, dot.y)
            document.set_dot_radius(dot.id, old_radius * 1.6)
            document.move_dot(dot.id, old_position[0] + 7, old_position[1] + 5)
            self.assertGreater(document.geometry_layer.get_dot(dot.id).radius_x, old_radius)
            self.assertEqual((document.geometry_layer.get_dot(dot.id).x, document.geometry_layer.get_dot(dot.id).y), (old_position[0] + 7, old_position[1] + 5))
            document.delete_selected()
            self.assertEqual(len(document.geometry_layer.dots), len(FIXTURE_DOTS) - 1)

            project_path = root / "editable-geometry.json"
            document.save(project_path)
            source.unlink()  # 恢复时源图片不存在，证明没有偷偷触发重新分析。
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
            restored = subprocess.run(
                [sys.executable, "-m", "reference2d_poc.restore_check", str(project_path)],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(restored.stdout)
            self.assertFalse(payload["reference_visible"])
            self.assertEqual(payload["geometry_count"], len(FIXTURE_DOTS) - 1)
            reopened = Document2D.load(project_path)
            self.assertNotIn(dot.id, {candidate.id for candidate in reopened.geometry_layer.dots})

    def test_recognizer_rejects_white_and_non_round_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            svg_path = Path(temp) / "mixed.svg"
            svg_path.write_text(
                '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">'
                '<circle id="white" cx="20" cy="20" r="9" fill="#fff"/>'
                '<path id="line" d="M 10 60 L 90 60 L 90 64 L 10 64 Z" fill="#000"/>'
                '<circle id="dot" cx="50" cy="30" r="8" fill="#000"/>'
                '</svg>',
                encoding="utf-8",
            )
            candidates = PrimitiveRecognizer().recognize(SVGParser().parse_file(svg_path).paths)
            outcomes = {candidate.source_id: candidate for candidate in candidates}
            self.assertFalse(outcomes["white"].accepted_as_dot)
            self.assertFalse(outcomes["line-000"].accepted_as_dot)
            self.assertTrue(outcomes["dot"].accepted_as_dot)


if __name__ == "__main__":
    unittest.main()
