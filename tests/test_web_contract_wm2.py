"""WM2 contract tests: project fidelity, transport safety and manufacturing identity."""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, RectElement, Reference
from ppg.foundation.storage import load_pattern_document, save_pattern_document
from xiaomang_pattern_lab.contracts import (
    ArtifactDTO, ContractError, ErrorDTO, EvaluateRequestDTO, EvaluateResponseDTO,
    ManufacturingBuildRequestDTO, ManufacturingBuildResponseDTO, PatternDocumentDTO,
    canonical_json, manufacturing_result_id, parse_json, require_current_revision,
)
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.placement_assignment import RandomSettings, ShapePoolEntry
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import (
    CompositeField, ConstantField, FieldMapping, FieldRegistry, SharedFieldEngine,
    SizeModifier, WaveField,
)
from xiaomang_pattern_lab.shared_modifiers import PositionModifier

from tests.test_manufacturing_service_wm1 import printed_pattern_document


ROOT = Path(__file__).resolve().parents[1]


def sample() -> PatternDocument:
    return PatternDocument(Canvas(80, 50, "mm", 1), Reference(""), [
        CircleElement("a", 10, 15, 5, 5), CircleElement("b", 30, 15, 8, 8),
    ])


class WebContractWM2Tests(unittest.TestCase):
    def test_import_boundary_fresh_process(self):
        code = (
            "import sys; import xiaomang_pattern_lab.contracts; "
            "assert all(k not in sys.modules for k in "
            "('tkinter', 'fastapi', 'starlette', 'ppg.xiaomang_pipeline', 'bpy')); "
            "print('CONTRACT_IMPORT_OK')"
        )
        env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CONTRACT_IMPORT_OK", result.stdout)

    def test_official_project_roundtrip_preserves_rich_state_and_evaluation(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            session = PatternLabSession(FoundationPipeline(None, None), folder, document=sample())
            graph = SharedFieldEngine(FieldRegistry([
                ConstantField("base", .5), WaveField("wave", wavelength=40),
                CompositeField("combined", "base", "wave", "multiply"),
            ]), [SizeModifier("size", "combined", FieldMapping(.5, 1.5))]).to_dict()
            session.document.fields = graph["fields"]
            session.document.modifiers = graph["modifiers"]
            session.add_modifier_layer("position", PositionModifier(mode="offset", offset_x=2).to_dict())
            session.update_shape_pool([ShapePoolEntry("circle", 50, True), ShapePoolEntry("star", 50, True)],
                                      enabled=True, seed=99)
            session.update_random_transforms(RandomSettings(enabled=True, seed=17, size_random=.2, occupancy=.9))
            session.select("a")
            session.replace_selected_shape("star")
            # Session effect edits rebuild the field graph; attach this valid
            # composite after those edits to exercise the final persisted state.
            session.document.fields = graph["fields"]
            session.document.modifiers = graph["modifiers"]
            saved = session.save_document(str(folder / "rich.pattern.json"))
            loaded = load_pattern_document(str(saved))
            before = deepcopy(loaded.to_dict())
            evaluated = evaluate_pattern_document(loaded)
            dto = PatternDocumentDTO.from_document(loaded, "doc-rich", 17)
            encoded = canonical_json(dto.to_dict())
            decoded = PatternDocumentDTO.from_dict(parse_json(encoded))
            restored = decoded.to_document()
            self.assertEqual(restored.to_dict(), before)
            self.assertEqual(evaluate_pattern_document(restored), evaluated)
            self.assertEqual(loaded.to_dict(), before)
            self.assertIn('"type":"composite"', encoded)
            self.assertIn("replacement_map", encoded)
            self.assertIn("random", encoded)
            self.assertEqual(decoded.document_revision, 17)
            self.assertEqual(encoded, canonical_json(decoded.to_dict()))

    def test_legacy_schema_one_project_roundtrip(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "v01.pattern.json"
            legacy = sample().to_dict()
            for key in ("fields", "modifiers", "transforms"):
                legacy.pop(key)
            path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
            loaded = load_pattern_document(str(path))
            dto = PatternDocumentDTO.from_document(loaded, "v01", 0)
            restored = PatternDocumentDTO.from_dict(parse_json(canonical_json(dto.to_dict()))).to_document()
            self.assertEqual(restored.to_dict(), loaded.to_dict())

    def test_local_asset_paths_are_replaced_and_rebindable(self):
        with TemporaryDirectory() as temporary:
            image = str(Path(temporary) / "reference.png")
            source_svg = str(Path(temporary) / "vectorized.svg")
            pattern = sample()
            pattern.reference.source_path = image
            pattern.reference.metadata["preprocessed_path"] = image
            pattern.metadata["source_svg"] = source_svg
            pattern.fields = [{"id": "image", "type": "image", "parameters": {"image_path": image}}]
            original = deepcopy(pattern.to_dict())
            dto = PatternDocumentDTO.from_document(pattern, "doc-image", 1, asset_bindings={image: "asset-123", source_svg: "asset-svg"})
            encoded = canonical_json(dto.to_dict())
            self.assertNotIn(image, encoded)
            self.assertNotIn(str(Path(temporary)), encoded)
            self.assertEqual(len(dto.assets), 4)
            self.assertEqual(dto.to_document(asset_sources={"asset-123": image, "asset-svg": source_svg}).to_dict(), original)
            self.assertEqual(dto.to_document().reference.source_path, "")
            with self.assertRaises(ContractError) as failure:
                PatternDocumentDTO.from_document(pattern, "doc-image", 1)
            self.assertEqual(failure.exception.code, "unbound_asset")

    def test_path_numeric_and_version_rejections(self):
        pattern = sample()
        pattern.metadata["local_file"] = r"C:\Users\private\secret.png"
        with self.assertRaises(ContractError) as path_error:
            PatternDocumentDTO.from_document(pattern, "doc", 0)
        self.assertEqual(path_error.exception.code, "local_path_forbidden")
        pattern.metadata.clear()
        pattern.elements[0].x = float("nan")
        with self.assertRaises(ContractError) as number_error:
            PatternDocumentDTO.from_document(pattern, "doc", 0)
        self.assertEqual(number_error.exception.code, "invalid_number")
        with self.assertRaises(ContractError):
            parse_json('{"value":NaN}')
        valid = PatternDocumentDTO.from_document(sample(), "doc", 0).to_dict()
        valid["schema_version"] = "2.0"
        with self.assertRaises(ContractError) as version_error:
            PatternDocumentDTO.from_dict(valid)
        self.assertEqual(version_error.exception.code, "invalid_schema_version")

    def test_revision_identity_and_request_roundtrip(self):
        dto = PatternDocumentDTO.from_document(sample(), "doc", 17)
        request = EvaluateRequestDTO(dto)
        self.assertEqual(EvaluateRequestDTO.from_dict(parse_json(canonical_json(request.to_dict()))), request)
        response = EvaluateResponseDTO.from_document(dto.to_document(), "doc", 17).to_dict()
        self.assertEqual(response["document_revision"], 17)
        self.assertEqual(len(response["geometry"]), 2)
        self.assertEqual(response["bounds_mm"]["units"], "mm")
        self.assertEqual(response["geometry"][0]["type"], "circle")
        self.assertEqual(EvaluateResponseDTO.from_dict(response).to_dict(), response)
        require_current_revision(17, 17)
        with self.assertRaises(ContractError) as stale:
            require_current_revision(17, 18)
        self.assertEqual(stale.exception.code, "stale_revision")
        bad = request.to_dict(); bad["document_revision"] = 18
        with self.assertRaises(ContractError):
            EvaluateRequestDTO.from_dict(bad)

    def test_real_printed_pattern_contract_build_and_result_identity(self):
        with TemporaryDirectory() as temporary:
            pattern, model = printed_pattern_document()
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=pattern)
            session.activate_grid(model)
            dto = PatternDocumentDTO.from_document(session.document, "printed-02", 0)
            restored = PatternDocumentDTO.from_dict(parse_json(canonical_json(dto.to_dict()))).to_document()
            rebuilt_session = PatternLabSession(FoundationPipeline(None, None), Path(temporary) / "roundtrip", document=restored)
            before = ManufacturingService().build(session, 2)
            after = ManufacturingService().build(rebuilt_session, 2)
            self.assertEqual(restored.to_dict(), session.document.to_dict())
            self.assertEqual(after.mesh_result.size, before.mesh_result.size)
            self.assertEqual(after.component_count, 3)
            self.assertTrue(after.mesh_report.is_watertight)
            self.assertAlmostEqual(after.mesh_result.size[0], 57.2169065, places=4)
            self.assertAlmostEqual(after.mesh_result.size[1], 19.8991871, places=4)
            self.assertEqual(after.mesh_result.size[2], 2)
            self.assertAlmostEqual(float(after.mesh_result.mesh.volume), float(before.mesh_result.mesh.volume), places=5)
            request = ManufacturingBuildRequestDTO("printed-02", session.revision, 2)
            self.assertEqual(ManufacturingBuildRequestDTO.from_dict(request.to_dict()), request)
            response = ManufacturingBuildResponseDTO.from_service_result(after, dto).to_dict()
            self.assertEqual(response["status"], "completed")
            self.assertEqual(response["component_count"], 3)
            self.assertEqual(response["bounds_mm"]["size_z"], 2)
            self.assertEqual(response["manufacturing_result_id"], manufacturing_result_id(dto, 2))
            self.assertEqual(ManufacturingBuildResponseDTO.from_dict(response).to_dict(), response)
            self.assertNotIn("mesh", response)
            self.assertNotIn("C:\\", canonical_json(response))
            changed = deepcopy(dto.document)
            changed["elements"][0]["x"] += 1
            wrong = PatternDocumentDTO(dto.document_id, dto.document_revision, changed)
            with self.assertRaises(ContractError) as stale:
                ManufacturingBuildResponseDTO.from_service_result(after, wrong)
            self.assertEqual(stale.exception.code, "stale_revision")

    def test_world_mm_scaling_for_geometry_and_bounds(self):
        doc = PatternDocument(Canvas(100, 100, "svg_user_unit", 0.5), Reference(""), [
            RectElement("rect", 20, 40, 10, 20),
        ])
        geometry = EvaluateResponseDTO.from_document(doc, "scaled", 1).to_dict()
        self.assertEqual(geometry["geometry"][0]["x"], 10)
        self.assertEqual(geometry["geometry"][0]["height"], 10)
        self.assertEqual(geometry["bounds_mm"]["min_x"], 7.5)
        self.assertEqual(geometry["bounds_mm"]["height"], 10)

    def test_failed_manufacturing_without_mm_mapping_has_no_fake_mm_bounds(self):
        with TemporaryDirectory() as temporary:
            doc = PatternDocument(Canvas(100, 100), Reference(""), [CircleElement("dot", 20, 20, 10, 10)])
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=doc)
            dto = PatternDocumentDTO.from_document(doc, "unscaled", 0)
            result = ManufacturingService().build(session, 2)
            response = ManufacturingBuildResponseDTO.from_service_result(result, dto).to_dict()
            self.assertEqual(response["status"], "failed")
            self.assertIsNone(response["bounds_mm"])
            self.assertIsNone(response["connectivity_summary"]["components"][0]["bounds"])
            self.assertIsNone(response["conversion_summary"]["bounds_mm"])

    def test_artifact_error_and_conversion_are_transport_safe(self):
        artifact = ArtifactDTO("artifact-stl", "stl", "model/stl", "model.stl", "mfg-123", 684, "a" * 64)
        self.assertEqual(artifact.to_dict()["manufacturing_result_id"], "mfg-123")
        self.assertEqual(ArtifactDTO.from_dict(artifact.to_dict()), artifact)
        with self.assertRaises(ContractError):
            ArtifactDTO("bad", "stl", "model/stl", r"C:\Users\private\model.stl").to_dict()
        error = ErrorDTO("stale_revision", "文档已更新", True)
        self.assertEqual(ErrorDTO.from_dict(error.to_dict()), error)
        for payload, parser in ((artifact.to_dict(), ArtifactDTO.from_dict), (error.to_dict(), ErrorDTO.from_dict)):
            payload["schema_version"] = "2.0"
            with self.assertRaises(ContractError) as version:
                parser(payload)
            self.assertEqual(version.exception.code, "invalid_schema_version")
        with self.assertRaises(ContractError):
            ErrorDTO("error", "bad", False, {"value": math.inf}).to_dict()
        with self.assertRaises(ContractError):
            ErrorDTO("error", r"无法读取 C:\Users\private\secret.png", False).to_dict()


if __name__ == "__main__":
    unittest.main()
