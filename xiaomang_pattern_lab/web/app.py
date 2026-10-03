"""WM3: thin HTTP adapter; geometry and STL remain in the existing engine."""
from __future__ import annotations

import logging
import math
import os
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from statistics import fmean
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from ppg.foundation import FoundationPipeline
from ppg.foundation import SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.faithful_mapping import FaithfulMappingAdapter
from xiaomang_pattern_lab.contracts import (
    ArtifactDTO, ContractError, CURRENT_WEB_SCHEMA_VERSION, EvaluateRequestDTO,
    EvaluateResponseDTO, ManufacturingBuildRequestDTO,
    ManufacturingBuildResponseDTO, PatternDocumentDTO, manufacturing_result_id, parse_json,
)
from xiaomang_pattern_lab.manufacturing_service import ManufacturingService
from xiaomang_pattern_lab.pattern_analyzer import PatternAnalyzer
from xiaomang_pattern_lab.parametric import ElementPrototype, GridParametricModel
from xiaomang_pattern_lab.parametric_families import AlongCurveParametricModel, RadialParametricModel
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.stl_export import STLExporter

from .assets import AssetResolver, MAX_ASSET_BYTES, NullAssetResolver, TemporaryAssetStore
from .http_errors import (
    WebError, contract_error_handler, internal_error_handler, web_error_handler,
)
from .runtime_store import InMemoryManufacturingResultStore, StoredManufacturingResult
from .preview_artifact import export_preview_glb
from .failure_snapshot import save_manufacturing_failure
from xiaomang_pattern_lab.fabric_plan import plan_from_fabric_config
from xiaomang_pattern_lab.fabric_preview import FabricPreviewCache, build_fabric_preview, preview_key


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
    recommended = analysis.recommended
    return analysis, {"document_id": dto.document_id,
                      "document_revision": dto.document_revision,
                      "recommended_family": recommended.family if recommended else None,
                      "confidence": recommended.confidence if recommended else 0.0,
                      "analysis_status": "matched" if recommended else "no_match"}


def _apply_pattern(dto: PatternDocumentDTO, family: str) -> dict[str, Any]:
    analysis, _ = _pattern_analysis(dto)
    candidates = {item.family: item for item in (*analysis.candidates, analysis.fallback)}
    candidate = candidates.get(family)
    if candidate is None or candidate.model is None or (family != "free" and not dto.document.get("elements")):
        reason = str(candidate.diagnostics.get("reason", "")) if candidate else "不支持的图案结构。"
        raise WebError("pattern_family_unavailable", "无法应用该图案结构：%s 可尝试其他结构或自由布局。" % reason)
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


def _desktop_pattern_action(dto: PatternDocumentDTO, action: str) -> dict[str, Any]:
    """Expose the desktop's explicit Session actions, never a manual layout fallback."""
    with TemporaryDirectory(prefix="xiaomang-pattern-action-") as temporary:
        session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=dto.to_document())
        if action == "convert_recommended":
            recommendation = session.analyze_families().recommended
            if recommendation is None or recommendation.model is None:
                raise WebError("no_recommendation", "当前没有可靠的推荐结构；可进入自由参数化。")
            if recommendation.family == "grid":
                session.activate_grid(recommendation.model)
            elif recommendation.family == "radial":
                session.activate_radial(recommendation.model)
            elif recommendation.family == "along_curve":
                session.activate_along_curve(recommendation.model)
            else:
                raise WebError("unsupported_family", "当前推荐结构暂不支持转换。")
        elif action == "enter_free":
            session.activate_free_parametric(session.analyze_families().fallback.model)
        elif action == "bake":
            if not session.has_parametric_model:
                raise WebError("not_parametric", "当前不是参数化结构，无需烘焙。")
            session.bake_to_free_elements()
        else:
            raise WebError("invalid_pattern_action", "不支持的参数化操作。")
        return replace(dto, document=session.require_document().to_dict(),
                       document_revision=dto.document_revision + 1).to_dict()


def _manual_layout(dto: PatternDocumentDTO, family: str, raw: dict[str, Any] | None = None):
    """Supply parameters to existing layout models, never to a second layout engine."""
    items = [item for item in dto.to_document().elements if item.visible and item.width > 0 and item.height > 0]
    if not items:
        raise WebError("empty_layout", "没有可用于转换的有效元素。")
    xs, ys = [item.x for item in items], [item.y for item in items]
    left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
    cx, cy = (left + right) / 2, (top + bottom) / 2
    width, height = fmean(item.width for item in items), fmean(item.height for item in items)
    count = len(items)
    prototype = ElementPrototype.from_element(items[0])
    if family == "grid":
        columns = max(1, math.ceil(math.sqrt(count * max(right - left, 1) / max(bottom - top, 1))))
        rows = max(1, math.ceil(count / columns))
        defaults = {"rows": rows, "columns": columns,
                    "spacing_x": max(width * 1.2, (right - left) / max(1, columns - 1)),
                    "spacing_y": max(height * 1.2, (bottom - top) / max(1, rows - 1)),
                    "offset_x": cx, "offset_y": cy}
    elif family == "radial":
        defaults = {"center_x": cx, "center_y": cy,
                    "radius": max((right - left) / 2, (bottom - top) / 2, width, height),
                    "count": count, "angular_offset": 0.0}
    elif family == "along_curve":
        defaults = {"count": count, "element_width": width, "element_height": height}
    else:
        raise WebError("invalid_layout", "不支持的手动图案结构。")
    values = dict(defaults)
    for key, value in (raw or {}).items():
        if key not in defaults or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise WebError("invalid_layout_parameter", "手动转换参数无效：%s。" % key)
        values[key] = float(value)
    for key in ("rows", "columns", "count"):
        if key in values and (values[key] < 1 or values[key] > 5000 or int(values[key]) != values[key]):
            raise WebError("invalid_layout_parameter", "%s 必须是 1～5000 的整数。" % key)
    if family == "grid" and values["rows"] * values["columns"] > 5000:
        raise WebError("invalid_layout_parameter", "矩阵元素总数不能超过 5000。")
    for key in ("spacing_x", "spacing_y", "radius", "element_width", "element_height"):
        if key in values and values[key] <= 0:
            raise WebError("invalid_layout_parameter", "%s 必须大于零。" % key)
    if family == "grid":
        model = GridParametricModel(rows=int(values["rows"]), columns=int(values["columns"]),
            spacing_x=values["spacing_x"], spacing_y=values["spacing_y"],
            offset_x=values["offset_x"], offset_y=values["offset_y"],
            element_width=width, element_height=height, prototype=prototype,
            lock_aspect=prototype.kind == "circle")
    elif family == "radial":
        model = RadialParametricModel(count=int(values["count"]), center_x=values["center_x"],
            center_y=values["center_y"], base_radius=values["radius"], end_radius=values["radius"],
            start_angle=values["angular_offset"], end_angle=values["angular_offset"] + 360,
            element_width=width, element_height=height, prototype=prototype)
    else:
        # A straight initial path is an explicit layout choice; later edits
        # use the existing AlongCurveParametricModel, not recognition output.
        path = [(left, cy), (right, cy)] if right > left else [(cx, top), (cx, bottom)]
        if path[0] == path[1]: path[1] = (path[0][0] + max(width, 1), path[0][1])
        model = AlongCurveParametricModel(path_points=path, count=int(values["count"]),
            element_width=values["element_width"], element_height=values["element_height"], prototype=prototype)
    return model, values


def _prepare_pattern(dto: PatternDocumentDTO, family: str, raw: dict[str, Any] | None):
    analysis, _ = _pattern_analysis(dto)
    candidate = {item.family: item for item in analysis.candidates}.get(family)
    direct = family == "free" or (raw is None and candidate is not None and candidate.model is not None)
    if direct:
        proposed = _apply_pattern(dto, family)
        return {"mode": "direct", "proposed_document": proposed, "parameters": {}}
    model, parameters = _manual_layout(dto, family, raw)
    with TemporaryDirectory(prefix="xiaomang-pattern-preview-") as temporary:
        session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=dto.to_document())
        if family == "grid": session.activate_grid(model)
        elif family == "radial": session.activate_radial(model)
        else: session.activate_along_curve(model)
        proposed = replace(dto, document=session.require_document().to_dict(),
                           document_revision=dto.document_revision + 1).to_dict()
    preview = EvaluateResponseDTO.from_document(session.require_document(), dto.document_id,
                                                 dto.document_revision + 1).to_dict()
    return {"mode": "manual", "proposed_document": proposed, "parameters": parameters,
            "preview": preview}


class ManufacturingBuildFailure(WebError):
    def __init__(self, code: str, message: str, validation_summary: dict | None = None) -> None:
        super().__init__(code, message)
        self.validation_summary = validation_summary


def _build(document, dto: PatternDocumentDTO, height_mm: float):
    # WM1's validated service still accepts a headless Session. It neither
    # imports Tk nor writes to the submitted PatternDocument.
    with TemporaryDirectory(prefix="xiaomang-wm3-") as temporary:
        session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document)
        session.revision = dto.document_revision
        try:
            result = ManufacturingService().build(session, height_mm)
        except ValueError as error:
            if "fabric_config" in document.metadata:
                raise ManufacturingBuildFailure("invalid_fabric_base", str(error)) from error
            raise
    response = ManufacturingBuildResponseDTO.from_service_result(result, dto)
    if not result.ready or result.mesh_result is None:
        summaries = (response.geometry_validation_summary, response.mesh_validation_summary or {})
        details = [issue.get("message") or issue.get("code") for summary in summaries
                   for issue in summary.get("issues", []) if issue.get("severity") == "error"]
        details.extend(item.get("message") or item.get("code")
                       for item in response.conversion_summary.get("skipped", []))
        if response.conversion_summary.get("input_count", 0) == 0:
            details.insert(0, "当前没有可制造的二维元素。")
        elif response.conversion_summary.get("converted_count", 0) == 0:
            details.append("没有可转换为制造网格的闭合二维几何。")
        reason = next((str(item) for item in details if item), None)
        raise ManufacturingBuildFailure(
            "manufacturing_validation_failed", reason or "制造检查未通过，请检查二维几何与网格报告。",
            {"geometry": response.geometry_validation_summary,
             "connectivity": response.connectivity_summary,
             "conversion": response.conversion_summary,
             "mesh": response.mesh_validation_summary},
        )
    result_id = response.manufacturing_result_id
    artifact = ArtifactDTO(
        artifact_id=result_id + "-stl", manufacturing_result_id=result_id,
        kind="stl", media_type="model/stl", filename=result_id + ".stl",
    ).to_dict()
    response.artifacts.append(artifact)
    plan = None
    fabric = document.metadata.get("fabric_config")
    if (isinstance(fabric, dict) and fabric.get("unit_cell") is not None
            and isinstance(fabric.get("placement"), dict)
            and fabric["placement"].get("mode", "area_fill") == "area_fill"):
        try:
            plan = plan_from_fabric_config(fabric, result.conversion.geometry.bounds)
        except (ValueError, TypeError, KeyError) as error:
            raise ManufacturingBuildFailure("invalid_fabric_base", str(error)) from error
    return result_id, StoredManufacturingResult(result, response.to_dict(), fabric_plan=plan)


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
               asset_store: TemporaryAssetStore | None = None,
               failure_snapshot_dir: Path | None = None,
               web_dist: Path | None = None) -> FastAPI:
    """Build an isolated headless server instance; importing does not start it."""
    resolver = asset_resolver if asset_resolver is not None else NullAssetResolver()
    store = result_store if result_store is not None else InMemoryManufacturingResultStore()
    fabric_preview_cache = FabricPreviewCache()
    uploads = asset_store if asset_store is not None else TemporaryAssetStore()
    snapshot_enabled = os.environ.get("XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS") == "1"
    staging_mode = (os.environ.get("XIAOMANG_STAGING") == "1"
                    or os.environ.get("XIAOMANG_ENV") == "staging")
    expensive_job_slot = threading.BoundedSemaphore(1) if staging_mode else None
    snapshot_dir = (failure_snapshot_dir if failure_snapshot_dir is not None else
                    Path(__file__).resolve().parents[2] / "work" / "manufacturing-failures")
    app = FastAPI(title="Xiaomang Pattern Lab API", version="0.3-alpha", debug=False,
                  docs_url=None if staging_mode else "/docs",
                  redoc_url=None if staging_mode else "/redoc",
                  openapi_url=None if staging_mode else "/openapi.json")
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
    def contract() -> dict:
        from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
        return {"schema_version": CURRENT_WEB_SCHEMA_VERSION, "units": "mm",
                "parameter_definitions": parameter_definitions()}

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

    @app.post("/api/v1/pattern-action", openapi_extra=JSON_DOCUMENT_BODY)
    async def pattern_action(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        if payload.get("document_revision") != dto.document_revision:
            raise ContractError("stale_revision", "文档已更改，请重新操作当前项目。")
        action = payload.get("action")
        if not isinstance(action, str):
            raise ContractError("invalid_document", "缺少参数化操作。")
        return JSONResponse(await run_in_threadpool(_desktop_pattern_action, dto, action))

    @app.post("/api/v1/prepare-pattern", openapi_extra=JSON_DOCUMENT_BODY)
    async def prepare_pattern(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        family = payload.get("family")
        parameters = payload.get("parameters")
        if not isinstance(family, str) or (parameters is not None and not isinstance(parameters, dict)):
            raise ContractError("invalid_document", "图案结构或转换参数无效。")
        if payload.get("document_revision") != dto.document_revision:
            raise ContractError("stale_revision", "文档已更改，请重新选择图案结构。")
        return JSONResponse(await run_in_threadpool(_prepare_pattern, dto, family, parameters))

    @app.post("/api/v1/manufacturing/build", openapi_extra=JSON_DOCUMENT_BODY)
    async def manufacturing_build(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        parameters = ManufacturingBuildRequestDTO.from_dict(payload)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        if (dto.document_id != parameters.document_id
                or dto.document_revision != parameters.document_revision):
            raise ContractError("invalid_document", "制造参数与文档身份不一致。")
        result_id = manufacturing_result_id(dto, parameters.height_mm)
        cached = store.get(result_id)
        if cached is not None:
            return JSONResponse(cached.response)
        if expensive_job_slot is not None and not expensive_job_slot.acquire(blocking=False):
            raise WebError("staging_busy", "测试站正在处理另一项三维任务，请稍后重试。")
        try:
            document = await run_in_threadpool(_resolve_document, dto, resolver)
            try:
                result_id, stored = await run_in_threadpool(_build, document, dto, parameters.height_mm)
            except ManufacturingBuildFailure as error:
                if snapshot_enabled:
                    try:
                        path = await run_in_threadpool(
                            save_manufacturing_failure, snapshot_dir, dto, parameters.height_mm,
                            error.code, error.validation_summary)
                        error.failure_id = path.stem
                        logging.getLogger(__name__).info("Manufacturing failure snapshot saved: failure_id=%s", path.stem)
                    except (OSError, ValueError, TypeError, ContractError) as snapshot_error:
                        logging.getLogger(__name__).warning(
                            "Manufacturing failure snapshot could not be saved (%s)",
                            type(snapshot_error).__name__)
                raise
            store.put(result_id, stored)
            return JSONResponse(stored.response)
        finally:
            if expensive_job_slot is not None:
                expensive_job_slot.release()

    @app.post("/api/v1/fabric/preview", openapi_extra=JSON_DOCUMENT_BODY)
    async def fabric_design_preview(request: Request) -> JSONResponse:
        payload = await _read_payload(request)
        dto = PatternDocumentDTO.from_dict(_document_payload(payload))
        if payload.get("document_revision") != dto.document_revision:
            raise ContractError("stale_revision", "文档已更改，请重新更新 Fabric 预览。")
        key = await run_in_threadpool(preview_key, dto)
        cached = fabric_preview_cache.get(key)
        if cached is not None:
            return JSONResponse({**cached, "cache_hit": True}, headers={"Cache-Control": "no-store"})
        if expensive_job_slot is not None and not expensive_job_slot.acquire(blocking=False):
            raise WebError("staging_busy", "测试站正在处理另一项三维任务，请稍后重试。")
        try:
            document = await run_in_threadpool(_resolve_document, dto, resolver)
            try:
                result = await run_in_threadpool(build_fabric_preview, document, dto)
            except (ValueError, TypeError, KeyError) as error:
                raise WebError("invalid_fabric_preview", str(error)) from error
            fabric_preview_cache.put(key, result)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        finally:
            if expensive_job_slot is not None:
                expensive_job_slot.release()

    @app.get("/api/v1/manufacturing/{manufacturing_result_id}/model.stl")
    def download_stl(manufacturing_result_id: str) -> Response:
        stored = store.get(manufacturing_result_id)
        if stored is None:
            raise WebError("artifact_not_found", "制造结果不存在或已经过期。")
        with stored.artifact_lock:
            if stored.stl_bytes is None:
                stored.stl_bytes = STLExporter().export_bytes(stored.result.mesh_result)
        artifact = stored.response["artifacts"][0]
        return Response(stored.stl_bytes, media_type="model/stl",
                        headers={"Content-Disposition": 'attachment; filename="%s"' % artifact["filename"]})

    @app.get("/api/v1/manufacturing/{manufacturing_result_id}/preview.glb")
    def download_preview(manufacturing_result_id: str) -> Response:
        stored = store.get(manufacturing_result_id)
        if stored is None:
            raise WebError("artifact_not_found", "三维预览不存在或已经过期，请重新检查并生成。")
        with stored.artifact_lock:
            if stored.preview_glb_bytes is None:
                stored.preview_glb_bytes = export_preview_glb(stored.result.mesh_result)
        return Response(stored.preview_glb_bytes, media_type="model/gltf-binary",
                        headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/manufacturing/{manufacturing_result_id}/fabric-plan")
    def fabric_plan(manufacturing_result_id: str) -> Response:
        stored = store.get(manufacturing_result_id)
        if stored is None:
            raise WebError("artifact_not_found", "制造结果不存在或已经过期。")
        if stored.fabric_plan is None:
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
        payload = stored.fabric_plan.preview_payload()
        payload["manufacturing_result_id"] = manufacturing_result_id
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    # Production assets are opt-in; local Vite + FastAPI development is unchanged.
    dist_setting = web_dist if web_dist is not None else os.environ.get("XIAOMANG_WEB_DIST")
    if dist_setting:
        dist = Path(dist_setting).resolve()
        index = dist / "index.html"
        assets = dist / "assets"
        if not index.is_file() or not assets.is_dir():
            raise RuntimeError("Web build is missing index.html or assets directory")
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

        @app.get("/favicon.svg", include_in_schema=False)
        def favicon() -> FileResponse:
            icon = dist / "favicon.svg"
            if not icon.is_file():
                raise HTTPException(status_code=404)
            return FileResponse(icon, media_type="image/svg+xml")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        def frontend(frontend_path: str) -> FileResponse:
            # Never turn unknown API or file requests into HTML, nor expose
            # server files outside the compiled frontend bundle.
            if (frontend_path in {"api", "docs", "redoc", "openapi.json"}
                    or frontend_path.startswith("api/") or "." in frontend_path):
                raise HTTPException(status_code=404)
            return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})

    return app
