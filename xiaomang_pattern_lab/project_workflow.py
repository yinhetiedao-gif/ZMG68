"""App settings and recovery IO, separate from the sole PatternDocument model."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from ppg.foundation.storage import atomic_write_json, migrate_pattern_payload
from ppg.foundation.models import PatternDocument
from ppg.runtime_paths import user_data_root


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            # Access denied means the process exists; don't offer its recovery.
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class ProjectFiles:
    """No geometry state. Only recent paths and recovery envelopes live here.

    Explicit data_root isolates tests; production uses the existing user-data
    helper regardless of cwd or source/frozen execution. Workspace namespaces
    prevent unrelated experiments from offering each other's recovery files.
    """

    def __init__(self, workspace: Path, data_root: Path | None = None):
        self.root = Path(data_root) if data_root is not None else user_data_root() / "projects"
        self.settings_path = self.root / "recent-projects.json"
        namespace = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()[:16]
        self.recovery_dir = self.root / "recovery" / namespace
        self.recovery_path = self.recovery_dir / (uuid4().hex + ".recovery.json")

    def recent(self) -> list[str]:
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return list(dict.fromkeys(p for p in raw.get("paths", [])
                                     if isinstance(p, str) and Path(p).is_absolute()))[:10]
        except (OSError, ValueError, TypeError, AttributeError):
            return []

    def remember(self, path: Path) -> None:
        value = str(path.resolve())
        paths = [p for p in self.recent() if os.path.normcase(p) != os.path.normcase(value)]
        atomic_write_json(self.settings_path, {"paths": [value, *paths][:10]})

    def forget(self, path: Path) -> None:
        value = os.path.normcase(str(path.resolve()))
        atomic_write_json(self.settings_path, {"paths": [p for p in self.recent()
                                                          if os.path.normcase(p) != value]})

    def write_recovery(self, document: PatternDocument, project_path: Path | None, revision: int) -> Path:
        document.validate()
        payload = {"recovery_version": 1, "owner_pid": os.getpid(),
                   "project_path": str(project_path) if project_path else None,
                   "revision": revision, "document": document.to_dict()}
        return atomic_write_json(self.recovery_path, payload, self.validate_recovery)

    @staticmethod
    def validate_recovery(payload: dict) -> PatternDocument:
        if payload.get("recovery_version") != 1:
            raise ValueError("不支持的恢复数据版本。")
        return PatternDocument.from_dict(migrate_pattern_payload(payload["document"]))

    def recoveries(self) -> list[Path]:
        result = []
        for path in self.recovery_dir.glob("*.recovery.json"):
            if path == self.recovery_path:
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.validate_recovery(raw)
                if not process_is_running(int(raw.get("owner_pid", 0))):
                    result.append(path)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue
        return sorted(result, key=lambda path: path.stat().st_mtime, reverse=True)

    def discard_recovery(self, path: Path | None = None) -> None:
        target = (path or self.recovery_path).resolve()
        if target.parent != self.recovery_dir.resolve() or not target.name.endswith(".recovery.json"):
            raise ValueError("恢复文件不属于当前工作区。")
        target.unlink(missing_ok=True)
