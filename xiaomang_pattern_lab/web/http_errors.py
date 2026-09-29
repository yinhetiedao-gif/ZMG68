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
    "invalid_asset": 422,
    "asset_not_found": 404,
    "import_failed": 422,
    "pattern_family_unavailable": 422,
    "internal_error": 500,
}


class WebError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def error_response(code: str, message: str) -> JSONResponse:
    status = HTTP_STATUS_BY_CODE.get(code, 500)
    return JSONResponse(status_code=status,
                        content=ErrorDTO(code, message, recoverable=status < 500).to_dict())


async def contract_error_handler(_request: Request, error: ContractError) -> JSONResponse:
    # Contract errors are expected client errors; no Python repr is exposed.
    return error_response(error.code, str(error))


async def web_error_handler(_request: Request, error: WebError) -> JSONResponse:
    return error_response(error.code, str(error))


async def internal_error_handler(_request: Request, error: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("WM3 server error", exc_info=error)
    return error_response("internal_error", "服务器处理失败，请稍后重试。")
