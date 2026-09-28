"""Headless application service for Pattern Lab's validated manufacturing chain.

Dependency direction is deliberately one-way::

    desktop UI / future API -> this service -> existing T/U/U.5/V/W/X engine

This module must remain importable without loading Tkinter.  It coordinates
the already validated session boundary, but owns no geometry, mesh, repair,
viewer, or file-dialog algorithms.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from .manufacturing_backend import ManufacturingBuildResult, ManufacturingMeshResult
from .manufacturing_geometry import ManufacturingConversionResult
from .mesh_validation import MeshValidationReport


def parse_height_mm(value: str | float) -> float:
    """Parse the single manufacturing parameter without touching a document."""

    try:
        height = float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("厚度必须是有效数字。") from error
    if not math.isfinite(height) or height <= 0:
        raise ValueError("厚度必须是大于 0 的有限毫米数值。")
    return height


@dataclass(frozen=True)
class ManufacturingServiceResult:
    """Application-level DTO shared by desktop UI and future transports.

    Engine-native reports remain available to Python callers.  A future Web
    contract can version and serialize them without exposing Tk state here.
    """

    height_mm: float
    geometry_report: Any
    connectivity_report: Any
    conversion: ManufacturingConversionResult
    build: ManufacturingBuildResult | None
    mesh_report: MeshValidationReport | None
    document_revision: int
    document_snapshot: dict
    ready: bool

    @property
    def mesh_result(self) -> ManufacturingMeshResult | None:
        return None if self.build is None else self.build.mesh_result

    @property
    def manufacturing_bounds_mm(self):
        return None if self.mesh_result is None else self.mesh_result.bounds

    @property
    def component_count(self) -> int:
        if self.mesh_report is not None:
            return self.mesh_report.component_count
        return self.connectivity_report.component_count

    @property
    def warnings(self) -> tuple[str, ...]:
        messages = list(self.conversion.report.warnings)
        if self.mesh_report is not None:
            messages.extend(issue.message for issue in self.mesh_report.issues if issue.severity == "warning")
        return tuple(messages)


class ManufacturingService:
    """Coordinate Gate T/U/U.5/V/W/X as a read-only derived operation."""

    def build(self, session, height_mm: float) -> ManufacturingServiceResult:
        height = parse_height_mm(height_mm)
        before = self._state(session)
        try:
            geometry = session.validate_final_geometry()
            connectivity = session.analyze_connectivity()
            conversion = session.adapt_manufacturing_geometry()
            build = None
            mesh = None
            if geometry.error_count == 0 and conversion.report.converted_count and not conversion.report.skipped_invalid_count:
                build = session.build_manufacturing_mesh(height_mm=height)
                mesh = session.validate_manufacturing_mesh(build.mesh_result)
        finally:
            self._assert_read_only(session, before)
        ready = bool(build is not None and mesh is not None and mesh.error_count == 0)
        return ManufacturingServiceResult(
            height, geometry, connectivity, conversion, build, mesh,
            session.revision, deepcopy(session.require_document().to_dict()), ready,
        )

    # Compatibility with the v0.2-M1 public wording while callers migrate to
    # the application-service vocabulary.
    prepare = build

    def is_current(self, session, result: ManufacturingServiceResult, height_text: str) -> bool:
        try:
            height = parse_height_mm(height_text)
        except ValueError:
            return False
        return bool(
            result.document_revision == session.revision
            and result.document_snapshot == session.require_document().to_dict()
            and math.isclose(result.height_mm, height, rel_tol=0.0, abs_tol=1e-12)
        )

    def export_stl(
        self,
        session,
        result: ManufacturingServiceResult,
        target: str | Path,
        *,
        overwrite: bool = False,
    ):
        if not result.ready or result.mesh_result is None:
            raise RuntimeError("制造检查尚未通过，不能导出 STL。")
        before = self._state(session)
        try:
            exported = session.export_validated_stl(result.mesh_result, target, overwrite=overwrite)
        finally:
            self._assert_read_only(session, before)
        return exported

    # Compatibility for existing desktop/tests.  New code should use the
    # explicit export_stl name.
    export = export_stl

    @staticmethod
    def _state(session):
        return (
            deepcopy(session.require_document().to_dict()), session.revision,
            session.saved_revision, session.undo_record_count, session.is_dirty,
        )

    @staticmethod
    def _assert_read_only(session, before) -> None:
        after = (
            session.require_document().to_dict(), session.revision,
            session.saved_revision, session.undo_record_count, session.is_dirty,
        )
        if before != after:
            raise RuntimeError("制造流程意外修改了当前设计，操作已停止。")


# Backward-compatible names are intentionally aliases, not a second workflow.
ManufacturingWorkflow = ManufacturingService
ManufacturingWorkflowResult = ManufacturingServiceResult
