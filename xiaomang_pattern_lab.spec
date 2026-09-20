# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir specification for Xiaomang Pattern Lab 0.1.0-dev."""
from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH).resolve()
EXTERNAL = ROOT / "external"
NODE_EXE = Path(os.environ["XIAOMANG_NODE_EXE"]).resolve()
DEBUG = os.environ.get("XIAOMANG_BUILD_CONFIGURATION", "release").lower() == "debug"

datas = []
binaries = []
datas += collect_data_files("xiaomang_pattern_lab", includes=["fixtures/*"])
datas += collect_data_files("ppg", includes=["locales/*.json"])
# The upstream MCP source includes Vite's development cache. It is never used
# by `dist/index.js`, creates >260-character Windows paths, and must not ship.
# Keep the actual distribution and its production dependency tree intact.
# Map it to the short `mcp/` path in the bundle to avoid Windows path limits.
def upstream_runtime_data():
    excluded = {".vite", ".vite-temp", ".github", "test", "docs"}
    for source in EXTERNAL.rglob("*"):
        relative = source.relative_to(EXTERNAL)
        if not source.is_file() or source.suffix == ".map" or any(part in excluded for part in relative.parts):
            continue
        if relative.name == "imagetosvg_bridge.cjs":
            yield (str(source), ".")
        elif relative.parts and relative.parts[0] == "imagetosvg-mcp":
            destination = Path("mcp").joinpath(*relative.parts[1:-1])
            yield (str(source), str(destination))

datas += list(upstream_runtime_data())
datas += [(str(NODE_EXE), "tools")]

hiddenimports = sorted(set(
    collect_submodules("xiaomang_pattern_lab")
    + collect_submodules("ppg")
    # Gate V imports these lazily so ordinary 2D startup remains light.  Make
    # their wheels explicit here for the next PACK build; this Gate does not
    # rebuild or ship an EXE.
    + collect_submodules("trimesh")
    + collect_submodules("shapely")
    + ["PIL.ImageTk", "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "vtracer"]
    + ["mapbox_earcut"]
))
binaries += collect_dynamic_libs("shapely")
binaries += collect_dynamic_libs("mapbox_earcut")

a = Analysis(
    [str(ROOT / "xiaomang_pattern_lab" / "desktop_entry.py")],
    pathex=[str(ROOT), str(ROOT / "build-tools" / "vtracer-runtime")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=["pytest"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="XiaomangPatternLab",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=DEBUG, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[],
               name="XiaomangPatternLab")
