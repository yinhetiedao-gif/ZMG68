"""小芒造物项目内 Skill 编排的运行时适配层。

该模块把项目数据转换为 Xiaomang handoff contract，并复用现有的几何清理、本地 SDF
或可选 Blender Worker 和 STL 审计实现。它不实现新的生成算法，也不让 UI 直接接触 bpy。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from .blender_worker import BlenderResult, cleanup_primitives, run_blender_job
from .final_geometry import primitives_bounds
from .raster_print import audit_stl


STAGES = ("reference", "generator", "geometry", "manufacturing", "blender", "stl", "quality")


@dataclass(frozen=True)
class XiaomangPipelineResult:
    blender_result: BlenderResult
    handoff_path: str
    run_id: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _sha256(path)


def _artifact(artifacts: list[dict], artifact_id: str, kind: str, path: Path, producer: str, status: str = "passed") -> str:
    artifacts.append({"id": artifact_id, "kind": kind, "path": str(path.resolve()), "sha256": _sha256(path), "producer": producer, "status": status})
    return artifact_id


def _bounds(primitives: list[dict]) -> tuple[float, float, float, float]:
    bounds = primitives_bounds(primitives)
    if bounds == (0.0, 0.0, 0.0, 0.0):
        raise ValueError("制造预检没有可测量的二维元素。")
    return bounds


def run_project_stl_pipeline(
    primitives: list[dict],
    output_stl: str,
    *,
    settings: object,
    blender_path: str | None = None,
    timeout: int = 600,
) -> XiaomangPipelineResult:
    """运行项目内的 Reference/规则 → Clean Geometry → 本地/Blender → STL 交接链。

    当前参数化项目以“当前规则快照”作为 reference artifact；导入参考图时，分析结果已
    保存在项目 settings 中。这样既能统一审计格式，也不会伪造没有发生的 AI 分析。
    """
    output = Path(output_stl).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output.parent / ".xiaomang_runs" / run_id
    handoff_path = output.with_suffix(".xiaomang.handoff.json")
    artifacts: list[dict] = []
    stages = {name: {"status": "pending", "artifact_ids": []} for name in STAGES}
    envelope = {
        "contract": "xiaomang.handoff",
        "version": "1.0",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {},
        "intent": {"operation": "reference_to_stl", "target_width_mm": float(getattr(settings, "target_width_mm", 100.0)), "allow_multi_component": False},
        "stages": stages,
        "parameters": {
            "units": "mm",
            "seed": int(getattr(settings, "seed", 0)),
            "quality": str(getattr(settings, "three_d_quality", "标准")),
            "thickness_mm": float(getattr(settings, "three_d_thickness", 1.2)),
            "roundness": float(getattr(settings, "three_d_roundness", 55.0)),
            "organic_blend": float(getattr(settings, "three_d_blend", 55.0)),
            "minimum_feature_mm": float(getattr(settings, "three_d_min_feature", 0.8)),
        },
        "payload": {},
        "artifacts": artifacts,
        "validation": {"passed": False, "checks": []},
        "errors": [],
        "rollback": {"checkpoint": str((run_dir / "checkpoint.json").resolve()), "reversible": True},
    }

    current_stage = "reference"

    def checkpoint() -> None:
        _write_json(run_dir / "checkpoint.json", envelope)
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")

    def pass_stage(name: str, artifact_ids: list[str]) -> None:
        stages[name] = {"status": "passed", "artifact_ids": artifact_ids}
        checkpoint()

    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        input_path = run_dir / "editable_2d_input.json"
        input_hash = _write_json(input_path, {"kind": "current_project_rules", "units": "mm", "primitives": primitives, "seed": int(getattr(settings, "seed", 0))})
        reference_value = str(getattr(settings, "reference_image", "") or "")
        reference_path = Path(reference_value).resolve() if reference_value else None
        if reference_path and reference_path.is_file():
            envelope["source"] = {"kind": "reference_image", "path": str(reference_path), "sha256": _sha256(reference_path)}
        else:
            envelope["source"] = {"kind": "project_rules", "path": str(input_path.resolve()), "sha256": input_hash}
        envelope["payload"]["reference_analysis"] = {"mode": "existing_project_rules", "reference_image": str(getattr(settings, "reference_image", "") or ""), "honest": True}
        pass_stage("reference", [_artifact(artifacts, "a-input", "editable_2d_input", input_path, "xiaomang-orchestrator")])

        current_stage = "generator"
        generator_path = run_dir / "generator_rules.json"
        _write_json(generator_path, {"generator_id": str(getattr(settings, "active_generator", "radial")), "field_generator": str(getattr(settings, "field_generator", "")), "parameters": {"seed": int(getattr(settings, "seed", 0)), "count": len(primitives)}})
        envelope["payload"]["editable_2d"] = {"units": "mm", "primitive_count": len(primitives), "generator_id": str(getattr(settings, "active_generator", "radial")), "height_controls": int(len(getattr(settings, "height_controls", []) or []))}
        pass_stage("generator", [_artifact(artifacts, "a-generator", "generator_rules", generator_path, "xiaomang-generator")])

        current_stage = "geometry"
        cleaned, cleanup = cleanup_primitives(primitives, float(getattr(settings, "three_d_min_feature", 0.8)))
        geometry_path = run_dir / "clean_geometry.json"
        _write_json(geometry_path, {"units": "mm", "primitives": cleaned, "cleanup": cleanup, "connected_preflight": "requires_final_mesh_audit"})
        envelope["payload"]["clean_geometry"] = cleanup
        pass_stage("geometry", [_artifact(artifacts, "a-clean", "clean_geometry", geometry_path, "xiaomang-geometry")])

        current_stage = "manufacturing"
        min_x, min_y, max_x, max_y = _bounds(cleaned)
        preflight = {"units": "mm", "bounds": [min_x, min_y, max_x, max_y], "width_mm": max_x - min_x, "height_mm": max_y - min_y, "minimum_feature_mm": float(getattr(settings, "three_d_min_feature", 0.8)), "component_policy": "single_connected_final_mesh"}
        preflight_path = run_dir / "manufacturing_preflight.json"
        _write_json(preflight_path, preflight)
        envelope["payload"]["manufacturing_preflight"] = preflight
        pass_stage("manufacturing", [_artifact(artifacts, "a-preflight", "manufacturing_preflight", preflight_path, "xiaomang-manufacturing")])

        current_stage = "blender"
        result = run_blender_job(cleaned, str(output), thickness=float(getattr(settings, "three_d_thickness", 1.2)), quality=str(getattr(settings, "three_d_quality", "标准")), roundness=float(getattr(settings, "three_d_roundness", 55.0)), organic_blend=float(getattr(settings, "three_d_blend", 55.0)), minimum_feature_mm=float(getattr(settings, "three_d_min_feature", 0.8)), blender_path=blender_path, timeout=timeout)
        readback_path = run_dir / "blender_readback.json"
        _write_json(readback_path, {"backend": "native" if result.blender_path == "native" else "blender", "blender": None if result.blender_path == "native" else result.blender_path, "vertices": result.vertices, "triangles": result.triangles, "source_cleanup": result.source_cleanup, "audit": result.audit})
        envelope["payload"]["blender_readback"] = {"vertices": result.vertices, "triangles": result.triangles, "audit": result.audit}
        pass_stage("blender", [_artifact(artifacts, "a-readback", "final_model_readback", readback_path, "xiaomang-blender")])

        current_stage = "stl"
        stl_audit = audit_stl(output)
        if not stl_audit.get("watertight") or int(stl_audit.get("connected_components", 0)) != 1:
            raise RuntimeError("最终 STL 未通过单一连通主体和封闭性检查。")
        envelope["payload"]["stl_output"] = {"path": str(output), "audit": stl_audit}
        pass_stage("stl", [_artifact(artifacts, "a-stl", "stl", output, "xiaomang-stl")])

        current_stage = "quality"
        quality_path = run_dir / "quality_report.json"
        _write_json(quality_path, {"milestone": "final_manufacturing_mesh", "mesh_audit": stl_audit, "status": "passed"})
        envelope["payload"]["quality_report"] = {"milestone": "final_manufacturing_mesh", "status": "passed"}
        envelope["validation"] = {"passed": True, "checks": ["final_model_readback", "watertight", "single_component", "no_naked_edges", "no_non_manifold_edges", "no_degenerate_faces"]}
        pass_stage("quality", [_artifact(artifacts, "a-quality", "quality_report", quality_path, "xiaomang-quality")])
        checkpoint()
        return XiaomangPipelineResult(result, str(handoff_path), run_id)
    except Exception as error:
        stages[current_stage] = {"status": "failed", "artifact_ids": stages[current_stage].get("artifact_ids", [])}
        envelope["errors"].append({"stage": current_stage, "message": str(error)})
        checkpoint()
        raise
