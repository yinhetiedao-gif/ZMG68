"""Headless persistence for PatternDocument."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import DOCUMENT_SCHEMA_VERSION, PatternDocument


def migrate_pattern_payload(payload: dict) -> dict:
    """Central disk-load boundary; schema 1 remains the current format."""
    if not isinstance(payload, dict) or "canvas" not in payload:
        raise ValueError("这不是有效的 PatternDocument 项目文件。")
    version = payload.get("schema_version", DOCUMENT_SCHEMA_VERSION)
    if isinstance(version, bool) or version != DOCUMENT_SCHEMA_VERSION:
        raise ValueError("不支持的项目版本：%s。请使用兼容版本打开。" % version)
    result = dict(payload)
    result.setdefault("schema_version", DOCUMENT_SCHEMA_VERSION)
    result.setdefault("reference", {"source_path": ""})
    result.setdefault("fields", [])
    result.setdefault("modifiers", [])
    return result


def atomic_write_json(target: Path, payload: dict, validator=None) -> Path:
    """Serialize, flush and validate beside target before one atomic replace."""
    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".pattern-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        restored = json.loads(temporary.read_text(encoding="utf-8"))
        if validator is not None:
            validator(restored)
        os.replace(str(temporary), str(target))
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def save_pattern_document(document: PatternDocument, path: str) -> Path:
    document.validate()
    return atomic_write_json(Path(path), document.to_dict(), PatternDocument.from_dict)


def load_pattern_document(path: str) -> PatternDocument:
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    return PatternDocument.from_dict(migrate_pattern_payload(payload))
