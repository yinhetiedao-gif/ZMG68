from __future__ import annotations

import json
from pathlib import Path

from .model import Project


def save_project(path: str, project: Project) -> None:
    Path(path).write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str) -> Project:
    return Project.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_preset(path: str, project: Project) -> None:
    data = project.to_dict(); data["preset_version"] = 1
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
