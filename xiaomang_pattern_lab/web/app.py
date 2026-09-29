"""WM3: thin HTTP adapter; geometry and STL remain in the existing engine."""
from __future__ import annotations

import hashlib
import logging
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ppg.foundation import FoundationPipeline
from ppg.foundation import SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.faithful_mapping import FaithfulMappingAdapter
from xiaomang_pattern_lab.contracts import (
    ArtifactDTO, ContractError, CURRENT_WEB_SCHEMA_VERSION, EvaluateRequestDTO,
    EvaluateResponseDTO, ManufacturingBuildRequestDTO,
    ManufacturingBuildResponseDTO, PatternDocumentDTO, parse_json,
)
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.pattern_analyzer import PatternAnalyzer
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter

from .assets import AssetResolver, MAX_ASSET_BYTES, NullAssetResolver, TemporaryAssetStore
from .http_errors import (
    WebError, contract_error_handler, internal_error_handler, web_error_handler,
)
from .runtime_store import InMemoryManufacturingResultStore, StoredManufacturingResult


MAX_REQUEST_BYTES = 2 * 1024 * 1024
LOCAL_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173",
                     "http://localhost:5174", "http://127.0.0.1:5174",
                     "http://localhost:3000", "http://127.0.0.1:3000")
JSON_DOCUMENT_BODY = {"requestBody": {"required": True, "content": {
    "application/json": {"schema": {"type": "object", "additionalProperties": True},
                         "description": "完整 WM2 DTO v1 JSON；字段语义见 docs/WEB_CONTRACT_V1.md。"}
}}}


async def _read_payload(request: Request) -> dict[str, Any]:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > MAX_REQUEST_BYTES:
                raise WebError("request_too_large", "请求内容超过 2 MiB 限制。")
        except ValueError as error:
            raise ContractError("invalid_json", "Content-Length 无效。") from error
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_BYTES:
            raise WebError("request_too_large", "请求内容超过 2 MiB 限制。")
    try:
        payload = parse_json(bytes(body).decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ContractError("invalid_json", "请求必须是 UTF-8 JSON。") from error
    if not isinstance(payload, dict):
        raise ContractError("invalid_document", "请求根节点必须是 JSON 对象。")
    return payload


def _resolve_document(dto: PatternDocumentDTO, resolver: AssetResolver):
    sources: dict[str, str] = {}
    for asset in dto.assets:
        identifier = asset.get("asset_id")
        if not isinstance(identifier, str) or not identifier:
            raise ContractError("invalid_document", "资产 ID 无效。")
        source = resolver.resolve(identifier)
        if not source or not Path(source).is_file():
            raise WebError("unresolved_asset", "资产尚未在服务器端登记或已失效。")
        sources[identifier] = source
    return dto.to_document(asset_sources=sources)


def _document_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document = payload.get("document")
    if not isinstance(document, dict):
        raise ContractError("invalid_document", "缺少有效的 PatternDocumentDTO。")
    return document


def _pattern_analysis(dto: PatternDocumentDTO):
    analysis = PatternAnalyzer().analyze_families(dto.to_document().elements)
    families = []
    for item in (*analysis.candidates, analysis.fallback):
        available = bool(item.model is not None and
                         (item.family == "free" or item.confidence >= 0.72) and
                         dto.document.get("elements"))
        families.append({"id": item.family, "confidence": item.confidence,
                         "available": available, "parameters": {
                             key: value for key, value in item.parameters.items()
                             if key != "path_points"},
                         "reason": str(item.diagnostics.get("reason", ""))})
    return analysis, {"document_id": dto.document_id,
                      "document_revision": dto.document_revision,
                      "recommended": analysis.recommended.family if analysis.recommended else "free",
                      "families": families, "warnings": []}


def _apply_pattern(dto: PatternDocumentDTO, family: str) -> dict[str, Any]:
    analysis, _ = _pattern_analysis(dto)
    candidates = {item.family: item for item in (*analysis.candidates, analysis.fallback)}
    candidate = candidates.get(family)
    if candidate is None or candidate.model is None or not dto.document.get("elements") or (
            family != "free" and candidate.confidence < 0.72):
        raise WebError("pattern_family_unavailable", "当前图案没有可靠的该结构识别结果，请重新分析或使用自由布局。")
    with TemporaryDirectory(prefix="xiaomang-pattern-") as temporary:
        session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=dto.to_document())
        if family == "grid":
            session.activate_grid(candidate.model)
        elif family == "radial":
            session.activate_radial(candidate.model)
        elif family == "along_curve":
            session.activate_along_curve(candidate.model)
        else:
            session.activate_free_parametric(candidate.model)
        return replace(dto, document=session.require_document().to_dict(),
                       document_revision=dto.document_revision + 1).to_dict()


def _build(document, dto: PatternDocumentDTO, height_mm: float):
    # WM1's validated service still accepts a headless Session. It neither
    # imports Tk nor writes to the submitted PatternDocument.
    with TemporaryDirectory(prefix="xiaomang-wm3-") as temporary:
        session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document)
        session.revision = dto.document_revision
        result = ManufacturingService().build(session, height_mm)
    response = ManufacturingBuildResponseDTO.from_service_result(result, dto)
    if not result.ready or result.mesh_result is None:
        raise WebError("manufacturing_validation_failed", "制造检查未通过，请检查二维几何与网格报告。")
    # Gate X validates the exact retained manufacturing mesh and emits the
    # bytes once. The download route only serves these same bytes.
    stl_bytes = STLExporter().export_bytes(result.mesh_result)
    result_id = response.manufacturing_result_id
    artifact = ArtifactDTO(
        artifact_id=result_id + "-stl", manufacturing_result_id=result_id,
        kind="stl", media_type="model/stl", filename=result_id + ".stl",
        byte_size=len(stl_bytes), sha256=hashlib.sha256(stl_bytes).hexdigest(),
    ).to_dict()
    response.artifacts.append(artifact)
    encoded = response.to_dict()
    return result_id, StoredManufacturingResult(result, encoded, stl_bytes)


def _import_asset(item) -> dict[str, Any]:
    """Use the desktop's existing replaceable raster/vector adapters, then DTO."""
    if item.media_type == "image/svg+xml":
        document = SVGNormalizer().normalize_file(str(item.path))
    else:
        processor = BinaryThresholdImageProcessingAdapter()
        vectorizer = ImageToSVGVectorizationAdapter(mode="simple")
        output = item.path.parent / item.asset_id / "vectorized.svg"
        output.parent.mkdir(exist_ok=True)
        document = FaithfulMappingAdapter(processor, vectorizer).map_raster(
            str(item.path), str(output)).document
    # Local temporary paths are server details, never Web Contract contents.
    document = deepcopy(document)
    document.reference.source_path = ""
    for section in (document.reference.metadata, document.reference.preprocessing):
        for key in list(section):
            if key.endswith("path"):
                section[key] = ""
    document.metadata["source_svg"] = ""
    document.metadata["source_asset_id"] = item.asset_id
    # SVG/pixel user units require a display mapping. This is explicitly not
    # a verified manufacturing scale; callers must confirm dimensions later.
    if document.canvas.mm_per_unit is None:
        document.canvas.mm_per_unit = 1.0
        document.metadata["web_import_scale_unconfirmed"] = True
    dto = PatternDocumentDTO.from_document(document, item.asset_id, 0)
    return dto.to_dict()


def create_app(*, asset_resolver: AssetResolver | None = None,
               result_store: InMemoryManufacturingResultStore | None = None,
               asset_store: TemporaryAssetStore | None = None) -> FastAPI:
    """Build an isolated headless server instance; importing does not start it."""
    resolver = asset_resolver if asset_resolver is not None else NullAssetResolver()
    store = result_store if result_store is not None else InMemoryManufacturingResultStore()
    uploads = asset_store if asset_store is not None else TemporaryAssetStore()
    app = FastAPI(title="Xiaomang Pattern Lab API", version="0.3-alpha")
    app.add_middleware(CORSMiddleware, allow_origins=list(LOCAL_DEV_ORIGINS),
                       allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Filename"])
    app.add_exception_handler(ContractError, contract_error_handler)
    app.add_exception_handler(WebError, web_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "contract_version": CURRENT_WEB_SCHEMA_VERSION}

    @app.get("/api/v1/contract")
    def contract() -> dict[str, str]:
        return {"schema_version": CURRENT_WEB_SCHEMA_VERSION, "units": "mm"}

    @app.post("/api/v1/assets")
    async def upload_asset(request: Request) -> JSONResponse:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"image/png", "image/jpeg", "image/svg+xml"}:
            raise WebError("invalid_asset", "仅支持 PNG、JPG/JPEG 和 SVG。")
        filename = unquote(request.headers.get("x-filename", "image"))
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_ASSET_BYTES:
                raise WebError("asset_too_large", "文件超过 8 MiB 限制。")
        try:
            item = await run_in_threadpool(uploads.put, bytes(data), media_type, filename)
        except OverflowError as error:
            raise WebError("asset_store_full", str(error)) from error
        except ValueError as error:
            raise WebError("invalid_asset", str(error)) from error
        return JSONResponse({"asset_id": item.asset_id, "media_type": item.media_type,
                             "filename": item.filename})

    @app.post("/api/v1/import", openapi_extra=JSON_DOCUMENT_BODY)
    async def import_asset(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        identifier = payload.get("asset_id")
        if not isinstance(identifier, str):
            raise WebError("invalid_asset", "缺少资产 ID。")
        item = uploads.get(identifier)
        if item is None:
            raise WebError("asset_not_found", "图片不存在或已经过期，请重新导入。")
        try:
            dto = await run_in_threadpool(_import_asset, item)
        except (ValueError, OSError, RuntimeError) as error:
            logging.getLogger(__name__).warning("WM5.5 import failed", exc_info=error)
            raise WebError("import_failed", "图片转换失败，请检查图片内容和本机转换服务。") from error
        return JSONResponse(dto)

    @app.post("/api/v1/evaluate", openapi_extra=JSON_DOCUMENT_BODY)
    async def evaluate(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        _document_payload(payload)
        dto = EvaluateRequestDTO.from_dict(payload)
        document = _resolve_document(dto.document, resolver)
        response = await run_in_threadpool(EvaluateResponseDTO.from_document,
                                           document, dto.document.document_id,
                                           dto.document.document_revision)
        return JSONResponse(response.to_dict())

    @app.post("/api/v1/analyze-pattern", openapi_extra=JSON_DOCUMENT_BODY)
    async def analyze_pattern(request: Request) -> JSONResponse:
        dto = PatternDocumentDTO.from_dict(_document_payload(await _read_payload(request)))
        _, result = await run_in_threadpool(_pattern_analysis, dto)
        return JSONResponse(result)

    @app.post("/api/v1/apply-pattern", openapi_extra=JSON_DOCUMENT_BODY)
    async def apply_pattern(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        family = payload.get("family")
        if not isinstance(family, str):
            raise ContractError("invalid_document", "缺少图案结构类型。")
        if payload.get("document_revision") != dto.document_revision:
            raise ContractError("stale_revision", "图案分析已过期，请重新分析当前项目。")
        result = await run_in_threadpool(_apply_pattern, dto, family)
        return JSONResponse(result)

    @app.post("/api/v1/manufacturing/build", openapi_extra=JSON_DOCUMENT_BODY)
    async def manufacturing_build(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        parameters = ManufacturingBuildRequestDTO.from_dict(payload)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        if (dto.document_id != parameters.document_id
                or dto.document_revision != parameters.document_revision):
            raise ContractError("invalid_document", "制造参数与文档身份不一致。")
        document = _resolve_document(dto, resolver)
        result_id, stored = await run_in_threadpool(_build, document, dto, parameters.height_mm)
        store.put(result_id, stored)
        return JSONResponse(stored.response)

    @app.get("/api/v1/manufacturing/{manufacturing_result_id}/model.stl")
    def download_stl(manufacturing_result_id: str) -> Response:
        stored = store.get(manufacturing_result_id)
        if stored is None:
            raise WebError("artifact_not_found", "制造结果不存在或已经过期。")
        artifact = stored.response["artifacts"][0]
        return Response(stored.stl_bytes, media_type="model/stl",
                        headers={"Content-Disposition": 'attachment; filename="%s"' % artifact["filename"]})

    return app
