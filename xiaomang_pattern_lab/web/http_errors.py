"""One stable ErrorDTO → HTTP mapping for the entire WM3 server."""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from xiaomang_pattern_lab.contracts import ContractError, ErrorDTO


HTTP_STATUS_BY_CODE = {
    "invalid_schema_version": 400,
    "invalid_json": 400,
    "invalid_document": 422,
    "invalid_height": 422,
    "invalid_number": 422,
    "invalid_transport_value": 422,
    "local_path_forbidden": 422,
    "unbound_asset": 422,
    "unresolved_asset": 422,
    "missing_mm_mapping": 422,
    "stale_revision": 409,
    "manufacturing_validation_failed": 422,
    "artifact_not_found": 404,
    "request_too_large": 413,
    "asset_too_large": 413,
    "asset_store_full": 429,
    "staging_busy": 429,
    "invalid_asset": 422,
    "asset_not_found": 404,
    "import_failed": 422,
    "pattern_family_unavailable": 422,
    "no_recommendation": 422,
    "unsupported_family": 422,
    "not_parametric": 422,
    "invalid_pattern_action": 422,
    "empty_layout": 422,
    "invalid_layout": 422,
    "invalid_layout_parameter": 422,
    "invalid_fabric_base": 422,
    "invalid_fabric_preview": 422,
    "internal_error": 500,
}


class WebError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def error_response(code: str, message: str, *, failure_id: str | None = None) -> JSONResponse:
    status = HTTP_STATUS_BY_CODE.get(code, 500)
    return JSONResponse(status_code=status,
                        content=ErrorDTO(code, message, recoverable=status < 500,
                                         details={"failure_id": failure_id} if failure_id else None).to_dict())


async def contract_error_handler(_request: Request, error: ContractError) -> JSONResponse:
    # Contract errors are expected client errors; no Python repr is exposed.
    return error_response(error.code, str(error))


async def web_error_handler(_request: Request, error: WebError) -> JSONResponse:
    return error_response(error.code, str(error), failure_id=getattr(error, "failure_id", None))


async def internal_error_handler(_request: Request, error: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("WM3 server error", exc_info=error)
    return error_response("internal_error", "服务器处理失败，请稍后重试。")
