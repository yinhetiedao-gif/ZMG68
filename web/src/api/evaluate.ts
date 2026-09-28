import { apiBaseUrl, EXPECTED_SCHEMA_VERSION } from './client'
import type { BoundsMM, EvaluateResponse, FinalGeometry, PatternDocumentDTO } from '../model/types'

export class EvaluateError extends Error {}

const supported = new Set(['circle', 'ellipse', 'rect', 'path', 'filled_region'])

function validBounds(value: unknown): value is BoundsMM {
  if (!value || typeof value !== 'object') return false
  const bounds = value as Record<string, unknown>
  return bounds.units === 'mm'
    && ['min_x', 'min_y', 'max_x', 'max_y', 'width', 'height'].every((key) => typeof bounds[key] === 'number' && Number.isFinite(bounds[key]))
}

function validGeometry(value: unknown): value is FinalGeometry {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return typeof item.id === 'string' && item.id.length > 0 && supported.has(String(item.type))
    && item.units === 'mm'
    && ['x', 'y', 'width', 'height', 'rotation'].every((key) => typeof item[key] === 'number' && Number.isFinite(item[key]))
    && (item.type !== 'path' && item.type !== 'filled_region'
      || typeof item.path_data === 'string' && item.path_data_coordinate_system === 'element_local')
}

export async function evaluateDocument(
  dto: PatternDocumentDTO, signal?: AbortSignal, fetcher: typeof fetch = fetch,
): Promise<EvaluateResponse> {
  let response: Response
  try {
    response = await fetcher(`${apiBaseUrl()}/api/v1/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        schema_version: EXPECTED_SCHEMA_VERSION,
        document_id: dto.document_id,
        document_revision: dto.document_revision,
        document: dto,
      }),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new EvaluateError('无法连接 Python 后端；当前项目仍在浏览器中，尚未求值。')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'message' in payload
      ? String(payload.message) : `HTTP ${response.status}`
    throw new EvaluateError(`二维求值失败：${message}`)
  }
  if (!payload || typeof payload !== 'object') throw new EvaluateError('二维求值返回格式无效。')
  const result = payload as Record<string, unknown>
  if (result.schema_version !== '1.0' || result.document_id !== dto.document_id
      || result.document_revision !== dto.document_revision
      || !Array.isArray(result.geometry) || !result.geometry.every(validGeometry)
      || (result.bounds_mm !== null && !validBounds(result.bounds_mm))
      || !Array.isArray(result.warnings)) {
    throw new EvaluateError('二维求值结果与项目版本、毫米单位或受支持几何不匹配。')
  }
  return result as unknown as EvaluateResponse
}
