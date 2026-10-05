import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'

export interface FabricFinalReport {
  schema_version: '1.0'; kind: 'final_fabric_mesh'
  document_id: string; document_revision: number; final_fabric_mesh_id: string
  final_fabric_mesh_ready: true; fused: true; export_available: boolean; stl_export_mode?: 'testing' | 'disabled'
  connected_component_count: number; watertight: boolean; volume_mm3: number
  bounds_mm: number[][]; interface_overlap_mm: number; cache_hit: boolean
  validation_report: { is_watertight: boolean; finite_coordinates: boolean;
    error_count: number; degenerate_face_count: number; component_count: number }
}

export class FabricRequestError extends Error {
  constructor(message: string, readonly diagnostics: Record<string, unknown>,
    readonly expired = false, readonly exportDisabled = false) { super(message) }
}

async function readResponse(response: Response): Promise<Record<string, any>> {
  const text = await response.text()
  let result: Record<string, any>
  try {
    result = JSON.parse(text)
    if (result === null || typeof result !== 'object' || Array.isArray(result)) throw new Error('invalid response')
  } catch {
    throw new FabricRequestError(`请求失败（HTTP ${response.status}）：后端未返回有效的结果数据。`,
      { http_status: response.status, stage: 'response_contract' })
  }
  if (!response.ok) {
    const failure = result.fusion_report
    const code = result.error?.code ?? (response.status === 404 ? 'route_not_found' : 'http_error')
    const reason = result.error?.message ?? (response.status === 404
      ? '当前后端没有此接口，请检查运行中的项目服务。'
      : typeof result.detail === 'string' ? result.detail : '后端未提供错误原因。')
    const failureId = failure?.failure_id ?? result.error?.details?.failure_id
    throw new FabricRequestError(`${reason}（HTTP ${response.status}）${failureId ? ` 失败编号：${failureId}。` : ''}`,
      { ...failure, http_status: response.status, error_code: code, response: result,
        stage: failure?.stage ?? 'request' },
      failure?.stage === 'stale_result' || code === 'stale_revision' || code === 'artifact_not_found',
      code === 'fabric_stl_disabled')
  }
  return result
}

export async function requestFabricFusion(dto: PatternDocumentDTO, signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<FabricFinalReport> {
  const response = await fetcher(`${apiBaseUrl()}/api/v1/fabric/fusion`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ document: dto, document_revision: dto.document_revision }),
  })
  const result = await readResponse(response)
  const validation = result.validation_report
  if (result.schema_version !== '1.0' || result.kind !== 'final_fabric_mesh'
    || result.document_id !== dto.document_id || result.document_revision !== dto.document_revision
    || result.final_fabric_mesh_ready !== true || result.fused !== true
    || !(result.export_available === false || result.export_available === true && result.stl_export_mode === 'testing')
    || typeof result.final_fabric_mesh_id !== 'string' || result.connected_component_count !== 1
    || result.watertight !== true || !Number.isFinite(result.volume_mm3) || result.volume_mm3 <= 0
    || !Number.isFinite(result.interface_overlap_mm) || result.interface_overlap_mm < 0
    || !validation || validation.is_watertight !== true || validation.finite_coordinates !== true
    || validation.error_count !== 0 || validation.degenerate_face_count !== 0 || validation.component_count !== 1
    || !Array.isArray(result.bounds_mm) || result.bounds_mm.length !== 2
    || !result.bounds_mm.every((row: unknown) => Array.isArray(row) && row.length === 3 && row.every(Number.isFinite))
    || !result.bounds_mm[1].every((v: number, i: number) => v > result.bounds_mm[0][i]))
    throw new FabricRequestError('最终制造网格响应与当前设计不匹配或未通过检查。',
      { stage: 'response_contract', response: result })
  return result as FabricFinalReport
}

export async function fetchFabricStl(report: FabricFinalReport, dto: PatternDocumentDTO,
  signal: AbortSignal, fetcher: typeof fetch = fetch): Promise<Blob> {
  if (!report.export_available || report.document_id !== dto.document_id
    || report.document_revision !== dto.document_revision) throw new Error('设计已变化，请重新生成后导出。')
  const response = await fetcher(`${apiBaseUrl()}/api/v1/fabric/${encodeURIComponent(report.final_fabric_mesh_id)}/model.stl`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ document: dto, document_revision: dto.document_revision }),
  })
  if (!response.ok) {
    await readResponse(response)
  }
  if (!response.headers.get('content-type')?.includes('model/stl')) throw new Error('STL 响应格式错误。')
  return response.blob()
}
