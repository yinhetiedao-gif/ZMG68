import { apiBaseUrl, EXPECTED_SCHEMA_VERSION } from './client'
import type { PatternDocumentDTO } from '../model/types'

export interface ManufacturingIssue { code?: string; severity?: string; message?: string }
export interface ManufacturingBuildResult {
  schema_version: '1.0'
  manufacturing_result_id: string
  document_id: string
  document_revision: number
  status: 'completed'
  geometry_validation_summary: { checked_count: number; error_count: number; warning_count: number; issues: ManufacturingIssue[] }
  connectivity_summary: { component_count: number; isolated_count: number }
  conversion_summary: { input_count: number; converted_count: number; skipped_count: number; warnings: string[] }
  mesh_validation_summary: { is_watertight: boolean; component_count: number; error_count: number; warning_count: number; issues: ManufacturingIssue[] } | null
  bounds_mm: { size_x: number; size_y: number; size_z: number; units: 'mm' } | null
  component_count: number
  warnings: string[]
}

export class ManufacturingError extends Error {}

export async function buildManufacturing(
  dto: PatternDocumentDTO, heightMm: number, signal?: AbortSignal, fetcher: typeof fetch = fetch,
): Promise<ManufacturingBuildResult> {
  if (!Number.isFinite(heightMm) || heightMm <= 0) throw new ManufacturingError('厚度必须大于 0 mm。')
  let response: Response
  try {
    response = await fetcher(`${apiBaseUrl()}/api/v1/manufacturing/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ schema_version: EXPECTED_SCHEMA_VERSION, document_id: dto.document_id,
        document_revision: dto.document_revision, height_mm: heightMm, document: dto }),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ManufacturingError('无法连接 Python 制造服务；设计画布未受影响。')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'message' in payload
      ? String(payload.message) : `HTTP ${response.status}`
    const details = payload && typeof payload === 'object' && 'details' in payload ? payload.details : null
    const failureId = details && typeof details === 'object' && 'failure_id' in details
      && typeof details.failure_id === 'string' ? details.failure_id : null
    throw new ManufacturingError(`制造检查失败：${message}${failureId ? ` · failure_id: ${failureId}` : ''}`)
  }
  if (!payload || typeof payload !== 'object') throw new ManufacturingError('制造服务返回格式无效。')
  const result = payload as Record<string, unknown>
  const bounds = result.bounds_mm as Record<string, unknown> | null
  if (result.schema_version !== '1.0' || result.status !== 'completed'
    || result.document_id !== dto.document_id || result.document_revision !== dto.document_revision
    || typeof result.manufacturing_result_id !== 'string' || !result.manufacturing_result_id
    || !Number.isInteger(result.component_count) || (result.component_count as number) < 0
    || !Array.isArray(result.warnings)
    || !result.geometry_validation_summary || !result.connectivity_summary || !result.conversion_summary
    || !result.mesh_validation_summary || !bounds || bounds.units !== 'mm'
    || !['size_x', 'size_y', 'size_z'].every((key) => typeof bounds[key] === 'number' && Number.isFinite(bounds[key]) && (bounds[key] as number) > 0)
    || Math.abs((bounds.size_z as number) - heightMm) > 1e-5) {
    throw new ManufacturingError('制造结果与当前文档版本、厚度或毫米单位不匹配。')
  }
  return result as unknown as ManufacturingBuildResult
}
