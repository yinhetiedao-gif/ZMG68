"""Runtime-safe paths for source and PyInstaller builds.

Only packaged resources belong beneath ``sys._MEIPASS``.  User-editable
projects, presets and recovery data always live outside the application bundle.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def application_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    """Return an immutable packaged/source resource path without using cwd."""
    return application_root().joinpath(*parts)


def user_data_root(application_name: str = "XiaomangPatternLab") -> Path:
    """Return a writable user-data root, never the installed EXE directory."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local).resolve() / application_name
    return Path.home() / ".local" / "share" / application_name
