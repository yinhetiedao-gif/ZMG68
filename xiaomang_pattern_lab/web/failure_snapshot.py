"""Opt-in, local-only evidence for failed manufacturing builds."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.contracts.v1 import canonical_json


_SECRET_KEY = re.compile(r"password|secret|token|credential|authorization|api[_-]?key", re.I)


def _redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.search(key) else _redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def save_manufacturing_failure(
    directory: Path, dto: PatternDocumentDTO, height_mm: float,
    error_code: str, validation_summary: dict | None, *, failure_id: str | None = None,
) -> Path:
    """Save a transport-safe request/report without browser state or server paths.

    The caller enables this explicitly in development and handles I/O errors so
    the original manufacturing error always remains the HTTP response.
    """
    timestamp = datetime.now(timezone.utc)
    if failure_id is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', failure_id):
        raise ValueError('Invalid failure identifier')
    failure_id = failure_id or f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:12]}"
    document = dto.to_dict()
    payload = _redact({
        "snapshot_version": 1,
        "failure_id": failure_id,
        "timestamp_utc": timestamp.isoformat(),
        "document_id": dto.document_id,
        "document_revision": dto.document_revision,
        "pattern_document_dto": document,
        "manufacturing_parameters": {"height_mm": height_mm},
        "height_mm": height_mm,
        "fabric_config": document["document"].get("metadata", {}).get("fabric_config"),
        "active_fields": [field for field in document["document"].get("fields", [])
                          if field.get("enabled", True)],
        "active_modifiers": [modifier for modifier in document["document"].get("modifiers", [])
                             if modifier.get("enabled", True)],
        "error_code": error_code,
        "validation_summary": validation_summary or {},
    })
    # The Web contract rejects absolute local paths and non-finite numbers.
    content = json.dumps(json.loads(canonical_json(payload)), ensure_ascii=False, indent=2)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{failure_id}.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content + "\n")
    return path
