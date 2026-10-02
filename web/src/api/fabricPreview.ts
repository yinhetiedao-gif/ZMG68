import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'

export interface FabricDesignPreview {
  schema_version: '1.0'
  kind: 'fabric_instance_preview'
  document_id: string
  document_revision: number
  preview_id: string
  placement_mode: 'area_fill' | 'pattern_points'
  element_count: number
  count: number
  active_count: number
  total_count: number
  skipped_count: number
  unmatched_reference_count: number
  preview_simplified: boolean
  prototype: { vertices: number[][]; faces: number[][] } | null
  instances: FabricPreviewInstance[]
  base_preview: { type: 'solid' | 'grid'; bounds_mm: number[]; thickness_mm: number;
    spacing_x_mm: number | null; spacing_y_mm: number | null; line_width_mm: number | null }
  timings_ms: { evaluate: number; plan_and_prototype: number; serialization: number }
  client_request_ms?: number
  cache_hit: boolean
}

export interface FabricPreviewInstance {
  id: string
  source_id: string | null
  final_geometry_id: string | null
  x_mm: number
  y_mm: number
  z_mm: number
  rotation_deg: number
  scale: number
  scale_x: number
  scale_y: number
  enabled: boolean
  cell_type: string
  base_width_mm: number | null
  base_depth_mm: number | null
  base_height_mm: number | null
  height_mm: number
}

export async function requestFabricPreview(dto: PatternDocumentDTO, signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<FabricDesignPreview> {
  const started = performance.now()
  const requestId = dto.document_id
  const requestRevision = dto.document_revision
  const response = await fetcher(`${apiBaseUrl()}/api/v1/fabric/preview`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ document: dto, document_revision: requestRevision }),
  })
  const raw: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = raw && typeof raw === 'object' && 'message' in raw ? String(raw.message) : `HTTP ${response.status}`
    throw new Error(`Fabric 设计预览失败：${message}`)
  }
  const payload = raw as FabricDesignPreview
  if (!payload || payload.kind !== 'fabric_instance_preview')
    throw new Error('Fabric 预览响应格式不正确。')
  if (payload.document_id !== requestId || payload.document_revision !== requestRevision)
    throw new Error(`Fabric 预览版本不匹配：请求 ${requestId} / revision ${requestRevision}，响应 ${String(payload.document_id)} / revision ${String(payload.document_revision)}。`)
  if (!Array.isArray(payload.instances) || payload.instances.length !== payload.count
    || !Number.isInteger(payload.total_count)
    || !Number.isInteger(payload.active_count) || payload.active_count < 0
    || payload.active_count > payload.count
    || payload.instances.some((instance) => !Number.isFinite(instance.x_mm)
      || !Number.isFinite(instance.y_mm) || !Number.isFinite(instance.rotation_deg)
      || !Number.isFinite(instance.scale_x) || !Number.isFinite(instance.scale_y)
      || !Number.isFinite(instance.scale) || instance.scale <= 0
      || !Number.isFinite(instance.height_mm) || instance.height_mm <= 0
      || typeof instance.base_height_mm !== 'number' || !Number.isFinite(instance.base_height_mm)
      || instance.base_height_mm <= 0
      || instance.scale_x <= 0 || instance.scale_y <= 0)
    || !payload.base_preview || !Array.isArray(payload.base_preview.bounds_mm))
    throw new Error('Fabric 预览数据不完整或格式过旧；请重启当前项目的 FastAPI 后端。')
  return { ...payload, client_request_ms: performance.now() - started }
}
