"""WM2 transport contracts. No UI, server, or manufacturing implementation lives here."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import ntpath
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, TypedDict

from ppg.foundation import PatternDocument
from ppg.foundation.storage import migrate_pattern_payload

from .version import CURRENT_WEB_SCHEMA_VERSION


class ContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Bounds2DDTO(TypedDict):
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    width: float
    height: float
    units: str


class Bounds3DDTO(TypedDict):
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    size_x: float
    size_y: float
    size_z: float
    units: str


class FinalGeometryDTO(TypedDict, total=False):
    type: str
    id: str
    x: float
    y: float
    width: float
    height: float
    rotation: float
    units: str
    path_data: str
    path_data_coordinate_system: str


class ValidationIssueDTO(TypedDict):
    code: str
    severity: str
    message: str
    element_id: str
    bounds: Bounds2DDTO | None
    metadata: dict[str, Any]


class GeometryValidationReportDTO(TypedDict):
    checked_count: int
    valid_count: int
    warning_count: int
    error_count: int
    issues: list[ValidationIssueDTO]


class ConnectivityReportDTO(TypedDict):
    total_elements: int
    component_count: int
    isolated_count: int
    isolated_ids: list[str]
    largest_component_size: int
    skipped_invalid_count: int
    components: list[dict[str, Any]]


def _version(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != CURRENT_WEB_SCHEMA_VERSION:
        raise ContractError("invalid_schema_version", "不支持的 Web Contract 版本。")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("invalid_document", "%s 必须是非空字符串。" % label)
    return value


def _revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("invalid_document", "document_revision 必须是非负整数。")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError("invalid_number", "%s 必须是有限数值。" % label)
    return float(value)


def _absolute_path(value: str) -> bool:
    return bool(
        ntpath.isabs(value) or PurePosixPath(value).is_absolute()
        or "file://" in value.lower()
        or re.search(r"[A-Za-z]:[\\/]", value)
        or re.search(r"\\\\[^\\\s]+\\[^\\\s]+", value)
        or re.search(r"(?<![\w:/])/(?:Users|home|tmp|var|mnt)/", value)
    )


def _safe(value: Any, label: str = "$", *, path_check: bool = True) -> Any:
    """Copy only standard JSON types; reject non-finite values and local paths."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _finite(value, label)
    if isinstance(value, str):
        if path_check and _absolute_path(value):
            raise ContractError("local_path_forbidden", "Web Contract 含有本机绝对路径：%s" % label)
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(item, "%s[%d]" % (label, index), path_check=path_check) for index, item in enumerate(value)]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ContractError("invalid_transport_value", "%s 的对象键必须是字符串。" % label)
        return {key: _safe(item, "%s.%s" % (label, key), path_check=path_check) for key, item in value.items()}
    raise ContractError("invalid_transport_value", "%s 含有不可传输的 Python 对象。" % label)


def canonical_json(value: Any) -> str:
    return json.dumps(_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _reject_constant(value: str) -> None:
    raise ContractError("invalid_number", "JSON 不允许 %s。" % value)


def parse_json(text: str) -> Any:
    """Strict JSON input: Python's permissive NaN/Infinity parser is disabled."""
    try:
        return _safe(json.loads(text, parse_constant=_reject_constant))
    except json.JSONDecodeError as error:
        raise ContractError("invalid_json", "JSON 格式无效。") from error


def _asset_id(path: str, bindings: Mapping[str, str] | None) -> str:
    identifier = None if bindings is None else bindings.get(path)
    if not identifier:
        raise ContractError("unbound_asset", "本机图片必须先绑定 asset_id 才能进入 Web Contract。")
    return _text(identifier, "asset_id")


@dataclass(frozen=True)
class PatternDocumentDTO:
    document_id: str
    document_revision: int
    document: dict[str, Any]
    assets: tuple[dict[str, str], ...] = ()

    @classmethod
    def from_document(
        cls, document: PatternDocument, document_id: str, document_revision: int,
        *, asset_bindings: Mapping[str, str] | None = None,
    ) -> "PatternDocumentDTO":
        payload = deepcopy(document).to_dict()  # official project representation, without mutating caller
        assets: list[dict[str, str]] = []
        reference = payload["reference"]
        path = reference.get("source_path", "")
        if path:
            identifier = _asset_id(path, asset_bindings)
            assets.append({"role": "reference", "asset_id": identifier, "media_type": "image/unknown"})
            reference["source_path"] = ""
        for index, field in enumerate(payload.get("fields", [])):
            if field.get("type") == "image":
                parameters = field.get("parameters", {})
                path = parameters.get("image_path", "")
                if path:
                    identifier = _asset_id(path, asset_bindings)
                    assets.append({"role": "field:%s" % field["id"], "asset_id": identifier, "media_type": "image/unknown"})
                    parameters["image_path"] = ""
        return cls(_text(document_id, "document_id"), _revision(document_revision), _safe(payload), tuple(assets))

    def to_dict(self) -> dict[str, Any]:
        return _safe({
            "schema_version": CURRENT_WEB_SCHEMA_VERSION,
            "document_id": self.document_id,
            "document_revision": self.document_revision,
            "document": self.document,
            "assets": list(self.assets),
        })

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PatternDocumentDTO":
        _version(payload)
        candidate = cls(
            _text(payload.get("document_id"), "document_id"),
            _revision(payload.get("document_revision")),
            _safe(payload.get("document")),
            tuple(_safe(payload.get("assets", []))),
        )
        candidate.to_document()  # validate the canonical project schema and element types
        return candidate

    def to_document(self, *, asset_sources: Mapping[str, str] | None = None) -> PatternDocument:
        payload = deepcopy(self.document)
        for asset in self.assets:
            try:
                role, identifier = asset["role"], asset["asset_id"]
            except (KeyError, TypeError) as error:
                raise ContractError("invalid_document", "资产引用结构无效。") from error
            path = "" if asset_sources is None else asset_sources.get(identifier, "")
            if role == "reference":
                payload["reference"]["source_path"] = path
            elif role.startswith("field:"):
                field_id = role[6:]
                matches = [field for field in payload.get("fields", []) if field.get("id") == field_id and field.get("type") == "image"]
                if len(matches) != 1:
                    raise ContractError("invalid_document", "图片场资产引用无法对应唯一 Field。")
                matches[0]["parameters"]["image_path"] = path
            else:
                raise ContractError("invalid_document", "未知资产角色。")
        try:
            return PatternDocument.from_dict(migrate_pattern_payload(payload))
        except (KeyError, TypeError, ValueError) as error:
            raise ContractError("invalid_document", "PatternDocument 数据无效：%s" % error) from error


def require_current_revision(expected: int, current: int) -> None:
    if _revision(expected) != _revision(current):
        raise ContractError("stale_revision", "文档版本已变化，请重新读取后再提交。")


def bounds2d(bounds, *, scale: float | None = 1.0) -> Bounds2DDTO | None:
    if bounds is None or scale is None:
        return None
    a, b, c, d = (_finite(value, "bounds2d") * scale for value in bounds)
    return _safe({"min_x": a, "min_y": b, "max_x": c, "max_y": d,
                  "width": c - a, "height": d - b, "units": "mm"})


def bounds3d(bounds) -> Bounds3DDTO | None:
    if bounds is None:
        return None
    lower, upper = bounds
    a, b, c = (_finite(value, "bounds3d") for value in lower)
    d, e, f = (_finite(value, "bounds3d") for value in upper)
    return _safe({"min_x": a, "min_y": b, "min_z": c,
                  "max_x": d, "max_y": e, "max_z": f,
                  "size_x": d - a, "size_y": e - b, "size_z": f - c, "units": "mm"})


def _scale(document: PatternDocument) -> float:
    canvas = document.canvas
    if canvas.mm_per_unit is not None:
        return _finite(canvas.mm_per_unit, "mm_per_unit")
    if canvas.unit == "mm":
        return 1.0
    raise ContractError("missing_mm_mapping", "画布没有毫米映射，无法生成世界毫米坐标。")


def final_geometry(document: PatternDocument) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Discriminated final elements, with world-mm placement and local SVG path data."""
    from xiaomang_pattern_lab.evaluation import evaluate_pattern_document

    scale = _scale(document)
    geometry: list[dict[str, Any]] = []
    extents: list[tuple[float, float, float, float]] = []
    for element in evaluate_pattern_document(document):
        if not element.visible:
            continue
        item = asdict(element)
        for key in ("x", "y", "width", "height", "base_x", "base_y", "base_width", "base_height", "rx", "ry"):
            if key in item:
                item[key] = _finite(item[key], key) * scale
        # SVG path coordinates are intrinsic element-local data; the placement
        # and base frame above are world-mm. Never treat path_data as screen px.
        if "path_data" in item:
            item["path_data_coordinate_system"] = "element_local"
        item["units"] = "mm"
        geometry.append(_safe(item))
        x, y, w, h = item["x"], item["y"], item["width"], item["height"]
        half = math.hypot(w, h) / 2.0 if item["rotation"] else None
        extents.append((x - (half if half is not None else w / 2), y - (half if half is not None else h / 2),
                        x + (half if half is not None else w / 2), y + (half if half is not None else h / 2)))
    if not extents:
        return geometry, None
    return geometry, bounds2d((min(v[0] for v in extents), min(v[1] for v in extents),
                               max(v[2] for v in extents), max(v[3] for v in extents)))


def geometry_validation_report(report, *, scale: float | None = 1.0) -> GeometryValidationReportDTO:
    return _safe({
        "checked_count": report.checked_count, "valid_count": report.valid_count,
        "warning_count": report.warning_count, "error_count": report.error_count,
        "issues": [{"code": issue.issue_type, "severity": issue.severity,
                    "message": issue.message, "element_id": issue.element_id,
                    "bounds": bounds2d(issue.bounds, scale=scale), "metadata": issue.metadata} for issue in report.issues],
    })


def connectivity_report(report, *, scale: float | None = 1.0) -> ConnectivityReportDTO:
    return _safe({
        "total_elements": report.total_element_count, "component_count": report.component_count,
        "isolated_count": report.isolated_count, "isolated_ids": list(report.isolated_element_ids),
        "largest_component_size": report.largest_component_size,
        "skipped_invalid_count": report.skipped_invalid_count,
        "components": [{"component_id": item.component_id, "element_ids": list(item.element_ids),
                        "element_count": item.element_count, "bounds": bounds2d(item.bounds, scale=scale)}
                       for item in report.components],
    })


def mesh_validation_report(report) -> dict[str, Any] | None:
    if report is None:
        return None
    return _safe({
        "vertex_count": report.vertex_count, "face_count": report.face_count,
        "is_watertight": report.is_watertight, "finite_coordinates": report.finite_coordinates,
        "boundary_edge_count": report.boundary_edge_count,
        "non_manifold_edge_count": report.non_manifold_edge_count,
        "degenerate_face_count": report.degenerate_face_count,
        "component_count": report.component_count,
        "warning_count": report.warning_count, "error_count": report.error_count,
        "issues": [{"code": issue.issue_type, "severity": issue.severity,
                    "message": issue.message, "component_index": issue.component_index,
                    "metadata": issue.metadata} for issue in report.issues],
    })


@dataclass(frozen=True)
class EvaluateRequestDTO:
    document: PatternDocumentDTO

    def to_dict(self) -> dict[str, Any]:
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "document_id": self.document.document_id,
                      "document_revision": self.document.document_revision,
                      "document": self.document.to_dict()})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvaluateRequestDTO":
        _version(payload)
        document = PatternDocumentDTO.from_dict(payload["document"])
        if payload.get("document_id") != document.document_id or payload.get("document_revision") != document.document_revision:
            raise ContractError("invalid_document", "Evaluate 外层与文档身份不一致。")
        return cls(document)


@dataclass(frozen=True)
class EvaluateResponseDTO:
    document_id: str
    document_revision: int
    geometry: list[dict[str, Any]]
    bounds_mm: dict[str, Any] | None
    warnings: list[str]

    @classmethod
    def from_document(cls, document: PatternDocument, document_id: str, revision: int) -> "EvaluateResponseDTO":
        geometry, bounds = final_geometry(document)
        return cls(document_id, revision, geometry, bounds, [])

    def to_dict(self) -> dict[str, Any]:
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "document_id": self.document_id, "document_revision": self.document_revision,
                      "geometry": self.geometry, "bounds_mm": self.bounds_mm, "warnings": self.warnings})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvaluateResponseDTO":
        _version(payload)
        result = cls(_text(payload.get("document_id"), "document_id"),
                     _revision(payload.get("document_revision")), payload.get("geometry"),
                     payload.get("bounds_mm"), payload.get("warnings"))
        safe = result.to_dict()
        if not isinstance(safe["geometry"], list) or not isinstance(safe["warnings"], list):
            raise ContractError("invalid_transport_value", "Evaluate Response 列表结构无效。")
        return result


@dataclass(frozen=True)
class ManufacturingBuildRequestDTO:
    document_id: str
    document_revision: int
    height_mm: float

    def to_dict(self) -> dict[str, Any]:
        height = _finite(self.height_mm, "height_mm")
        if height <= 0:
            raise ContractError("invalid_height", "厚度必须大于零。")
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "document_id": _text(self.document_id, "document_id"),
                      "document_revision": _revision(self.document_revision), "height_mm": height})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ManufacturingBuildRequestDTO":
        _version(payload)
        result = cls(payload.get("document_id"), payload.get("document_revision"), payload.get("height_mm"))
        result.to_dict()
        return result


def manufacturing_result_id(document_dto: PatternDocumentDTO, height_mm: float) -> str:
    request = ManufacturingBuildRequestDTO(document_dto.document_id, document_dto.document_revision, height_mm)
    digest = hashlib.sha256(canonical_json({"document": document_dto.to_dict(),
                                            "parameters": request.to_dict()}).encode("utf-8")).hexdigest()
    return "mfg-" + digest[:24]


@dataclass(frozen=True)
class ManufacturingBuildResponseDTO:
    manufacturing_result_id: str
    document_id: str
    document_revision: int
    status: str
    geometry_validation_summary: dict[str, Any]
    connectivity_summary: dict[str, Any]
    conversion_summary: dict[str, Any]
    mesh_validation_summary: dict[str, Any] | None
    bounds_mm: dict[str, Any] | None
    component_count: int
    warnings: list[str]
    artifacts: list[dict[str, Any]]

    @classmethod
    def from_service_result(cls, result, document_dto: PatternDocumentDTO) -> "ManufacturingBuildResponseDTO":
        require_current_revision(document_dto.document_revision, result.document_revision)
        snapshot = deepcopy(result.document_snapshot)
        for asset in document_dto.assets:
            if asset["role"] == "reference":
                snapshot["reference"]["source_path"] = ""
            elif asset["role"].startswith("field:"):
                field_id = asset["role"][6:]
                for field in snapshot.get("fields", []):
                    if field.get("id") == field_id and field.get("type") == "image":
                        field["parameters"]["image_path"] = ""
        if _safe(snapshot) != document_dto.document:
            raise ContractError("stale_revision", "制造结果与指定文档内容不一致。")
        report = result.conversion.report
        try:
            scale = _scale(document_dto.to_document())
        except ContractError as error:
            if error.code != "missing_mm_mapping" or result.ready:
                raise
            scale = None
        return cls(
            manufacturing_result_id(document_dto, result.height_mm), document_dto.document_id,
            document_dto.document_revision, "completed" if result.ready else "failed",
            geometry_validation_report(result.geometry_report, scale=scale),
            connectivity_report(result.connectivity_report, scale=scale),
            _safe({"input_count": report.input_count, "converted_count": report.converted_count,
                   "skipped_count": report.skipped_count, "skipped_invalid_count": report.skipped_invalid_count,
                   "skipped_open_count": report.skipped_open_count, "units": report.units,
                   "bounds_mm": bounds2d(report.bounds),
                   "skipped": [{"element_id": item.element_id, "code": item.reason, "message": item.message}
                               for item in report.skipped],
                   "warnings": list(report.warnings),
                   "topology_changed_element_ids": list(report.topology_changed_element_ids)}),
            mesh_validation_report(result.mesh_report), bounds3d(result.manufacturing_bounds_mm),
            result.component_count, list(result.warnings), [],
        )

    def to_dict(self) -> dict[str, Any]:
        if self.status not in {"queued", "running", "completed", "failed"}:
            raise ContractError("invalid_transport_value", "未知制造状态。")
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "manufacturing_result_id": self.manufacturing_result_id,
                      "document_id": self.document_id, "document_revision": self.document_revision,
                      "status": self.status, "geometry_validation_summary": self.geometry_validation_summary,
                      "connectivity_summary": self.connectivity_summary,
                      "conversion_summary": self.conversion_summary,
                      "mesh_validation_summary": self.mesh_validation_summary,
                      "bounds_mm": self.bounds_mm, "component_count": self.component_count,
                      "warnings": self.warnings, "artifacts": self.artifacts})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ManufacturingBuildResponseDTO":
        _version(payload)
        result = cls(*(
            payload.get(key) for key in (
                "manufacturing_result_id", "document_id", "document_revision", "status",
                "geometry_validation_summary", "connectivity_summary", "conversion_summary",
                "mesh_validation_summary", "bounds_mm", "component_count", "warnings", "artifacts",
            )
        ))
        safe = result.to_dict()
        if not isinstance(safe["artifacts"], list) or not isinstance(safe["warnings"], list):
            raise ContractError("invalid_transport_value", "制造结果列表结构无效。")
        return result


@dataclass(frozen=True)
class ArtifactDTO:
    artifact_id: str
    kind: str
    media_type: str
    filename: str
    manufacturing_result_id: str | None = None
    byte_size: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.kind not in {"svg", "stl", "glb"}:
            raise ContractError("invalid_transport_value", "未知 Artifact 类型。")
        if _absolute_path(self.filename) or "/" in self.filename or "\\" in self.filename:
            raise ContractError("local_path_forbidden", "Artifact filename 只能是文件名。")
        if self.byte_size is not None and (isinstance(self.byte_size, bool) or not isinstance(self.byte_size, int) or self.byte_size < 0):
            raise ContractError("invalid_transport_value", "Artifact byte_size 无效。")
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "artifact_id": self.artifact_id, "manufacturing_result_id": self.manufacturing_result_id,
                      "kind": self.kind, "media_type": self.media_type, "filename": self.filename,
                      "byte_size": self.byte_size, "sha256": self.sha256})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactDTO":
        _version(payload)
        result = cls(*(
            payload.get(key) for key in (
                "artifact_id", "kind", "media_type", "filename", "manufacturing_result_id", "byte_size", "sha256",
            )
        ))
        result.to_dict()
        return result


@dataclass(frozen=True)
class ErrorDTO:
    code: str
    message: str
    recoverable: bool
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return _safe({"schema_version": CURRENT_WEB_SCHEMA_VERSION,
                      "code": _text(self.code, "code"), "message": self.message,
                      "recoverable": self.recoverable, "details": self.details})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ErrorDTO":
        _version(payload)
        result = cls(payload.get("code"), payload.get("message"), payload.get("recoverable"), payload.get("details"))
        result.to_dict()
        return result
