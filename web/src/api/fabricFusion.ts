import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'

export interface FabricFinalReport {
  schema_version: '1.0'; kind: 'final_fabric_mesh'
  document_id: string; document_revision: number; final_fabric_mesh_id: string
  final_fabric_mesh_ready: true; fused: true; export_available: false
  connected_component_count: number; watertight: boolean; volume_mm3: number
  bounds_mm: number[][]; interface_overlap_mm: number; cache_hit: boolean
  validation_report: { is_watertight: boolean; finite_coordinates: boolean;
    error_count: number; degenerate_face_count: number; component_count: number }
}

export async function requestFabricFusion(dto: PatternDocumentDTO, signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<FabricFinalReport> {
  const response = await fetcher(`${apiBaseUrl()}/api/v1/fabric/fusion`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ document: dto, document_revision: dto.document_revision }),
  })
  const result = await response.json()
  if (!response.ok) {
    const failure = result.fusion_report
    throw new Error(`${result.error?.message ?? '最终制造网格生成失败。'}${failure ?
      ` 阶段：${failure.stage}；失败编号：${failure.failure_id}。` : ''}`)
  }
  const validation = result.validation_report
  if (result.schema_version !== '1.0' || result.kind !== 'final_fabric_mesh'
    || result.document_id !== dto.document_id || result.document_revision !== dto.document_revision
    || result.final_fabric_mesh_ready !== true || result.fused !== true || result.export_available !== false
    || typeof result.final_fabric_mesh_id !== 'string' || result.connected_component_count !== 1
    || result.watertight !== true || !Number.isFinite(result.volume_mm3) || result.volume_mm3 <= 0
    || !Number.isFinite(result.interface_overlap_mm) || result.interface_overlap_mm < 0
    || !validation || validation.is_watertight !== true || validation.finite_coordinates !== true
    || validation.error_count !== 0 || validation.degenerate_face_count !== 0 || validation.component_count !== 1
    || !Array.isArray(result.bounds_mm) || result.bounds_mm.length !== 2
    || !result.bounds_mm.every((row: unknown) => Array.isArray(row) && row.length === 3 && row.every(Number.isFinite))
    || !result.bounds_mm[1].every((v: number, i: number) => v > result.bounds_mm[0][i]))
    throw new Error('最终制造网格响应与当前设计不匹配或未通过检查。')
  return result as FabricFinalReport
}
