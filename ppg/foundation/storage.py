"""Headless persistence for PatternDocument."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import PatternDocument


def save_pattern_document(document: PatternDocument, path: str) -> Path:
    document.validate()
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(temporary), str(target))
    return target


def load_pattern_document(path: str) -> PatternDocument:
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    return PatternDocument.from_dict(payload)
