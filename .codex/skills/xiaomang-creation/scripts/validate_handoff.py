#!/usr/bin/env python3
"""Validate a Xiaomang handoff envelope without external dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


STAGE_ORDER = ["reference", "generator", "geometry", "manufacturing", "blender", "stl", "quality"]
STATUSES = {"pending", "running", "passed", "failed"}


def _is_abs(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and Path(value).is_absolute()


def validate_contract(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"contract", "version", "run_id", "created_at", "source", "intent", "stages", "artifacts", "validation", "rollback"}
    errors.extend(f"missing:{key}" for key in sorted(required - set(doc)))
    if errors:
        return errors
    if doc.get("contract") != "xiaomang.handoff":
        errors.append("contract must be xiaomang.handoff")
    if doc.get("version") != "1.0":
        errors.append("version must be 1.0")
    source = doc["source"]
    if not isinstance(source, dict) or not _is_abs(source.get("path")) or not source.get("sha256"):
        errors.append("source.path must be absolute and source.sha256 is required")
    intent = doc["intent"]
    if not isinstance(intent, dict) or intent.get("operation") != "reference_to_stl" or not isinstance(intent.get("target_width_mm"), (int, float)) or intent["target_width_mm"] <= 0:
        errors.append("intent must define reference_to_stl and positive target_width_mm")
    stages = doc["stages"]
    if not isinstance(stages, dict):
        errors.append("stages must be an object")
        stages = {}
    for index, stage_name in enumerate(STAGE_ORDER):
        stage = stages.get(stage_name)
        if not stage:
            continue
        status = stage.get("status") if isinstance(stage, dict) else None
        if status not in STATUSES:
            errors.append(f"invalid status:{stage_name}")
        if status == "passed":
            for previous in STAGE_ORDER[:index]:
                if previous in stages and stages[previous].get("status") != "passed":
                    errors.append(f"stage gate:{stage_name} requires {previous}=passed")
                    break
    artifacts = doc["artifacts"]
    artifact_ids: set[str] = set()
    if not isinstance(artifacts, list):
        errors.append("artifacts must be an array")
        artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("artifact must be an object")
            continue
        aid = artifact.get("id")
        if not aid or aid in artifact_ids:
            errors.append(f"duplicate or empty artifact id:{aid}")
        artifact_ids.add(aid)
        if not _is_abs(artifact.get("path")):
            errors.append(f"artifact path not absolute:{aid}")
        if not artifact.get("sha256") or not artifact.get("producer") or artifact.get("status") not in STATUSES:
            errors.append(f"artifact metadata incomplete:{aid}")
    for stage_name, stage in stages.items():
        for aid in stage.get("artifact_ids", []) if isinstance(stage, dict) else []:
            if aid not in artifact_ids:
                errors.append(f"unknown artifact:{stage_name}:{aid}")
    validation = doc["validation"]
    if not isinstance(validation, dict) or not isinstance(validation.get("passed"), bool) or not isinstance(validation.get("checks"), list):
        errors.append("validation must contain boolean passed and checks array")
    if stages.get("stl", {}).get("status") == "passed":
        for gate in ("manufacturing", "blender", "quality"):
            if stages.get(gate, {}).get("status") != "passed":
                errors.append(f"stl gate:{gate}=passed required")
        if not validation.get("passed", False):
            errors.append("stl cannot pass when validation.passed is false")
    rollback = doc["rollback"]
    if not isinstance(rollback, dict) or not _is_abs(rollback.get("checkpoint")) or not isinstance(rollback.get("reversible"), bool):
        errors.append("rollback.checkpoint must be absolute and reversible must be boolean")
    return errors


def main() -> int:
    try:
        if len(sys.argv) > 1:
            doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        else:
            doc = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid-json:{exc}")
        return 2
    if not isinstance(doc, dict):
        print("contract must be a JSON object")
        return 1
    errors = validate_contract(doc)
    if errors:
        print("handoff invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    print("handoff valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

