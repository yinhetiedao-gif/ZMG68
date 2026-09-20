"""Gate X: faithful Binary STL serialization behind Gate W validation.

STL has no unit metadata.  Pattern Lab therefore authors all numeric vertex
coordinates in millimetres and records that explicit convention in the export
result; this module never rescales a validated manufacturing Mesh.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Any

from .manufacturing_backend import ManufacturingMeshResult
from .mesh_validation import MeshValidationReport, MeshValidator


@dataclass(frozen=True)
class STLExportResult:
    output_path: Path
    format: str
    units_assumption: str
    vertex_count: int
    face_count: int
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    component_count: int
    warnings: tuple[str, ...]
    file_size_bytes: int
    validation_summary: MeshValidationReport


class STLExportBlockedError(RuntimeError):
    """Raised before any file write when Gate W reports a blocking error."""

    def __init__(self, report: MeshValidationReport) -> None:
        super().__init__("Mesh 制造检查未通过，已阻止 STL 导出。")
        self.report = report


class STLExporter:
    """Binary STL writer with no mesh repair, scaling, union, or viewer work."""

    format = "binary_stl"
    units_assumption = "mm"

    def __init__(self, *, validator: MeshValidator | None = None) -> None:
        self.validator = validator or MeshValidator()

    def export(
        self, mesh_result: ManufacturingMeshResult, output_path: str | Path, *, overwrite: bool = False,
    ) -> STLExportResult:
        """Validate then serialize a Mesh to Binary STL without mutating it.

        A pre-existing destination is rejected by default.  An explicit
        ``overwrite=True`` is the only path allowed to replace it.
        """

        report = self.validator.validate(mesh_result)
        if report.error_count:
            raise STLExportBlockedError(report)
        target = Path(output_path).expanduser()
        if target.suffix.lower() != ".stl":
            raise ValueError("STL 导出路径必须使用 .stl 扩展名。")
        if not target.parent.is_dir():
            raise FileNotFoundError("STL 导出目录不存在：%s" % target.parent)
        if target.exists() and not overwrite:
            raise FileExistsError("目标 STL 已存在；请明确允许覆盖：%s" % target)

        payload = _binary_stl_bytes(mesh_result.mesh)
        # Do not create a partial output on failed validation.  For ordinary
        # exports `xb` also prevents a concurrent process from silently being
        # overwritten after the existence check.
        if overwrite:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".%s." % target.name, suffix=".tmp", dir=target.parent,
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        else:
            with open(target, "xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())

        warnings = tuple(_export_warning(issue.issue_type) for issue in report.issues if issue.severity == "warning")
        return STLExportResult(
            output_path=target.resolve(),
            format=self.format,
            units_assumption=self.units_assumption,
            vertex_count=report.vertex_count,
            face_count=report.face_count,
            bounds=mesh_result.bounds,
            component_count=report.component_count,
            warnings=warnings,
            file_size_bytes=target.stat().st_size,
            validation_summary=report,
        )

    @staticmethod
    def reload_as_mesh_result(path: str | Path) -> ManufacturingMeshResult:
        """Read an STL for test/readback verification without processing it."""

        try:
            import numpy as np
            import trimesh
        except ImportError as error:
            raise RuntimeError("缺少 STL 读回依赖 trimesh。") from error
        source = Path(path)
        raw_mesh = trimesh.load_mesh(source, file_type="stl", process=False, maintain_order=True)
        # Binary STL stores each facet as three coordinate triples and has no
        # vertex-index table.  Reconstruct equal-coordinate indexes only in
        # this readback copy so Gate W can measure the file's topology.  This
        # neither changes the authored source Mesh nor edits the STL bytes;
        # it is not a repair, merge-by-tolerance, or geometry cleanup.
        raw_vertices = np.asarray(raw_mesh.vertices, dtype=float)
        raw_faces = np.asarray(raw_mesh.faces, dtype=int)
        vertices, inverse = np.unique(raw_vertices, axis=0, return_inverse=True)
        faces = inverse[raw_faces]
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
        lower, upper = mesh.bounds
        bounds = (
            (float(lower[0]), float(lower[1]), float(lower[2])),
            (float(upper[0]), float(upper[1]), float(upper[2])),
        )
        return ManufacturingMeshResult(
            mesh=mesh,
            bounds=bounds,
            vertex_count=int(len(vertices)),
            face_count=int(len(faces)),
            # Gate W recomputes actual components; STL itself stores none.
            component_count=0,
            height_mm=float(upper[2] - lower[2]),
            backend_name="stl-binary-readback",
            is_watertight=False,
        )


def _binary_stl_bytes(mesh: Any) -> bytes:
    try:
        from trimesh.exchange.stl import export_stl
    except ImportError as error:
        raise RuntimeError("缺少 Binary STL 导出依赖 trimesh。") from error
    payload = export_stl(mesh)
    if not isinstance(payload, bytes) or not payload:
        raise RuntimeError("Binary STL 序列化未返回有效字节。")
    return payload


def _export_warning(issue_type: str) -> str:
    if issue_type == "multiple_components":
        return "multiple_disconnected_components"
    return issue_type
