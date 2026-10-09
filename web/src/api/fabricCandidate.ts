import { apiBaseUrl } from './client'
import { HttpRequestError } from './requestErrors'
import type { PatternDocumentDTO } from '../model/types'
import { fabricOutputMode, type FabricOutputMode } from '../document/fabricBase'

export interface FabricCandidateReport {
  schema_version: '1.0'; kind: 'fabric_manufacturing_candidate'
  document_id: string; document_revision: number
  output_mode?: FabricOutputMode
  fused: false; export_available: false
  status: 'checked' | 'warning' | 'error'
  instance_count: number; enabled_instance_count: number
  bounds_mm: number[][] | null
  attachment_counts: Record<'ATTACHED' | 'MARGINAL' | 'DETACHED' | 'INVALID', number> & { VALID?: number }
  issues: { level: string; code: string; message: string }[]
  attachments: { instance_id: string; source_id: string | null; final_geometry_id: string | null;
    status: string; contact_area_mm2: number; gap_mm: number | null;
    issues: { level: string; code: string; message: string }[] }[]
}

export async function requestFabricCandidate(dto: PatternDocumentDTO, signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<FabricCandidateReport> {
  const response = await fetcher(`${apiBaseUrl()}/api/v1/fabric/candidate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ document: dto, document_revision: dto.document_revision }),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new HttpRequestError(response.status, data)
  if (!data) throw new Error('可制造性检查响应格式不正确。')
  const counts = data.output_mode === 'cells_only' ? ['ATTACHED', 'MARGINAL', 'DETACHED', 'INVALID', 'VALID'] : ['ATTACHED', 'MARGINAL', 'DETACHED', 'INVALID']
  if (data.schema_version !== '1.0' || data.kind !== 'fabric_manufacturing_candidate'
    || data.document_id !== dto.document_id || data.document_revision !== dto.document_revision
    || (data.output_mode ?? 'cells_with_base') !== fabricOutputMode(dto)
    || data.fused !== false || data.export_available !== false
    || !['checked', 'warning', 'error'].includes(data.status)
    || !Number.isInteger(data.instance_count) || data.instance_count < 0
    || !Number.isInteger(data.enabled_instance_count) || data.enabled_instance_count < 0
    || data.enabled_instance_count > data.instance_count
    || !counts.every(key => Number.isInteger(data.attachment_counts?.[key]) && data.attachment_counts[key] >= 0)
    || counts.reduce((sum, key) => sum + data.attachment_counts[key], 0) !== data.enabled_instance_count
    || !Array.isArray(data.attachments) || data.attachments.length !== data.enabled_instance_count
    || !Array.isArray(data.issues)
    || data.bounds_mm !== null && !(Array.isArray(data.bounds_mm) && data.bounds_mm.length === 2
      && data.bounds_mm.every((row: unknown) => Array.isArray(row) && row.length === 3 && row.every(Number.isFinite))))
    throw new Error('可制造性响应与当前设计不匹配或格式不完整。')
  return data as FabricCandidateReport
}
