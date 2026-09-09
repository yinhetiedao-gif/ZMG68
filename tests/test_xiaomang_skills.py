import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ppg.blender_worker import BlenderResult
from ppg.raster_print import audit_stl
from ppg.xiaomang_pipeline import run_project_stl_pipeline


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".codex" / "skills" / "xiaomang-creation"
SKILLS = [
    "xiaomang-creation",
    "xiaomang-orchestrator",
    "xiaomang-reference",
    "xiaomang-reference-reconstruction",
    "xiaomang-generator",
    "xiaomang-geometry",
    "xiaomang-blender",
    "xiaomang-native",
    "xiaomang-manufacturing",
    "xiaomang-stl",
    "xiaomang-quality",
]


class XiaomangSkillContractTests(unittest.TestCase):
    def test_all_skill_entrypoints_exist_and_have_frontmatter(self):
        for name in SKILLS:
            path = SKILL_ROOT / name / "SKILL.md" if name != "xiaomang-creation" else SKILL_ROOT / "SKILL.md"
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            self.assertRegex(text, r"(?m)^name:\s*" + re.escape(name) + r"\s*$")
            self.assertRegex(text, r"(?m)^description:\s*.+$")

    def test_handoff_schema_is_valid_json_and_declares_gate_fields(self):
        schema_path = SKILL_ROOT / "references" / "handoff_contract.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["contract"]["const"], "xiaomang.handoff")
        self.assertEqual(schema["properties"]["version"]["const"], "1.0")
        for field in ("source", "intent", "stages", "artifacts", "validation", "rollback"):
            self.assertIn(field, schema["required"])

    def test_contract_reference_mentions_full_pipeline_and_gates(self):
        text = (SKILL_ROOT / "references" / "handoff-contract.md").read_text(encoding="utf-8")
        for token in ("reference_analysis", "editable_2d", "clean_geometry", "blender_readback", "manufacturing_preflight", "stl_output", "quality_report"):
            self.assertIn(token, text)
        self.assertIn("只有在 Blender 读回、制造预检和质量审计通过", text)

    def test_no_third_party_runtime_copy_is_declared(self):
        text = (SKILL_ROOT / "references" / "third-party-adoption.md").read_text(encoding="utf-8")
        self.assertIn("不复制任何第三方仓库的代码", text)
        self.assertIn("不把第三方 Skill 变成新的 UI 或 Generator", text)

    def test_handoff_validator_accepts_complete_passed_chain(self):
        artifact_kinds = ["analysis_json", "editable_svg", "geometry_json", "preflight", "blend_readback", "stl", "quality_report"]
        artifacts = [
            {"id": f"a-{index}", "kind": kind, "path": f"C:/tmp/xiaomang/{kind}.json", "sha256": "abc", "producer": "test", "status": "passed"}
            for index, kind in enumerate(artifact_kinds)
        ]
        stages = {
            name: {"status": "passed", "artifact_ids": [f"a-{index}"]}
            for index, name in enumerate(("reference", "generator", "geometry", "manufacturing", "blender", "stl", "quality"))
        }
        doc = {
            "contract": "xiaomang.handoff", "version": "1.0", "run_id": "test-run", "created_at": "2026-08-27T00:00:00Z",
            "source": {"kind": "reference_image", "path": "C:/tmp/xiaomang/reference.png", "sha256": "src"},
            "intent": {"operation": "reference_to_stl", "target_width_mm": 100.0, "allow_multi_component": False},
            "stages": stages, "parameters": {"units": "mm", "seed": 1}, "artifacts": artifacts,
            "validation": {"passed": True, "checks": []}, "errors": [],
            "rollback": {"checkpoint": "C:/tmp/xiaomang/checkpoints/geometry.json", "reversible": True},
        }
        script = SKILL_ROOT / "scripts" / "validate_handoff.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(script)], input=json.dumps(doc), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("handoff valid", result.stdout)

    def test_handoff_validator_rejects_stl_without_quality_gate(self):
        doc = {
            "contract": "xiaomang.handoff", "version": "1.0", "run_id": "bad-run", "created_at": "2026-08-27T00:00:00Z",
            "source": {"kind": "reference_image", "path": "C:/tmp/reference.png", "sha256": "src"},
            "intent": {"operation": "reference_to_stl", "target_width_mm": 100.0},
            "stages": {
                "reference": {"status": "passed", "artifact_ids": []},
                "geometry": {"status": "passed", "artifact_ids": []},
                "manufacturing": {"status": "passed", "artifact_ids": []},
                "blender": {"status": "passed", "artifact_ids": []},
                "stl": {"status": "passed", "artifact_ids": []},
            },
            "artifacts": [], "validation": {"passed": True, "checks": []}, "rollback": {"checkpoint": "C:/tmp/checkpoint.json", "reversible": True},
        }
        script = SKILL_ROOT / "scripts" / "validate_handoff.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(script)], input=json.dumps(doc), text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stl gate:quality=passed required", result.stdout)

    def test_program_stl_export_writes_handoff_contract(self):
        def fake_blender_job(primitives, output_stl, **_kwargs):
            path = Path(output_stl)
            # 四面体：最小但完整的单一封闭网格，用于隔离测试编排层。
            faces = [
                ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
                ((0, 0, 0), (0, 0, 1), (1, 0, 0)),
                ((0, 0, 0), (0, 1, 0), (0, 0, 1)),
                ((1, 0, 0), (0, 0, 1), (0, 1, 0)),
            ]
            with path.open("wb") as handle:
                handle.write(b"test".ljust(80, b"\0")); handle.write(struct.pack("<I", len(faces)))
                for a, b, c in faces:
                    handle.write(struct.pack("<12fH", 0.0, 0.0, 1.0, *a, *b, *c, 0))
            audit = audit_stl(path)
            return BlenderResult(str(path), 4, 4, "fake-blender", "", {"删除元素": 0}, audit)

        settings = SimpleNamespace(target_width_mm=100.0, seed=7, three_d_quality="标准", three_d_thickness=1.2, three_d_roundness=55.0, three_d_blend=55.0, three_d_min_feature=0.8, active_generator="radial", field_generator="")
        with tempfile.TemporaryDirectory() as temp, patch("ppg.xiaomang_pipeline.run_blender_job", side_effect=fake_blender_job):
            output = Path(temp) / "model.stl"
            result = run_project_stl_pipeline([{"kind": "dot", "x": 5, "y": 5, "size": 2}], str(output), settings=settings, blender_path="fake-blender")
            document = json.loads(Path(result.handoff_path).read_text(encoding="utf-8"))
            self.assertTrue(output.exists())
            self.assertEqual(document["stages"]["quality"]["status"], "passed")
            self.assertTrue(document["validation"]["passed"])
            self.assertTrue(all(Path(item["path"]).is_absolute() for item in document["artifacts"]))


if __name__ == "__main__":
    unittest.main()
