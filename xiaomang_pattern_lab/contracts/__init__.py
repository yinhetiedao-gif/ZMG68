"""Versioned, JSON-only transport boundary for a future Web client."""

from .version import CURRENT_WEB_SCHEMA_VERSION
from .v1 import (
    ArtifactDTO,
    Bounds2DDTO,
    Bounds3DDTO,
    ConnectivityReportDTO,
    ContractError,
    ErrorDTO,
    EvaluateRequestDTO,
    EvaluateResponseDTO,
    FinalGeometryDTO,
    GeometryValidationReportDTO,
    ManufacturingBuildRequestDTO,
    ManufacturingBuildResponseDTO,
    PatternDocumentDTO,
    ValidationIssueDTO,
    bounds2d,
    bounds3d,
    canonical_json,
    connectivity_report,
    final_geometry,
    geometry_validation_report,
    manufacturing_result_id,
    mesh_validation_report,
    parse_json,
    require_current_revision,
)

__all__ = [name for name in globals() if not name.startswith("_")]
