"""WM3: thin HTTP adapter; geometry and STL remain in the existing engine."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ppg.foundation import FoundationPipeline
from xiaomang_pattern_lab.contracts import (
    ArtifactDTO, ContractError, CURRENT_WEB_SCHEMA_VERSION, EvaluateRequestDTO,
    EvaluateResponseDTO, ManufacturingBuildRequestDTO,
    ManufacturingBuildResponseDTO, PatternDocumentDTO, parse_json,
)
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter

from .assets import AssetResolver, NullAssetResolver
from .http_errors import (
    WebError, contract_error_handler, internal_error_handler, web_error_handler,
)
from .runtime_store import InMemoryManufacturingResultStore, StoredManufacturingResult


MAX_REQUEST_BYTES = 2 * 1024 * 1024
LOCAL_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173",
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


def create_app(*, asset_resolver: AssetResolver | None = None,
               result_store: InMemoryManufacturingResultStore | None = None) -> FastAPI:
    """Build an isolated headless server instance; importing does not start it."""
    resolver = asset_resolver if asset_resolver is not None else NullAssetResolver()
    store = result_store if result_store is not None else InMemoryManufacturingResultStore()
    app = FastAPI(title="Xiaomang Pattern Lab API", version="0.3-alpha")
    app.add_middleware(CORSMiddleware, allow_origins=list(LOCAL_DEV_ORIGINS),
                       allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])
    app.add_exception_handler(ContractError, contract_error_handler)
    app.add_exception_handler(WebError, web_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "contract_version": CURRENT_WEB_SCHEMA_VERSION}

    @app.get("/api/v1/contract")
    def contract() -> dict[str, str]:
        return {"schema_version": CURRENT_WEB_SCHEMA_VERSION, "units": "mm"}

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
