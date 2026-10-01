import { apiBaseUrl } from './client'

export class ArtifactError extends Error {}

export interface FabricInstancePreview {
  schema_version: '1.0'
  kind: 'fabric_instance_preview'
  manufacturing_result_id: string
  cell_type: string
  count: number
  prototype: { vertices: number[][]; faces: number[][] }
  instances: { id: string; x_mm: number; y_mm: number; z_mm: number; rotation_deg: number; scale: number }[]
  manufacturing_status: 'preview_only_not_in_stl'
}

export async function fetchFabricPlan(resultId: string, signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<FabricInstancePreview | null> {
  const response = await fetcher(`${apiBaseUrl()}/api/v1/manufacturing/${encodeURIComponent(resultId)}/fabric-plan`,
    { method: 'GET', signal })
  if (response.status === 204) return null
  if (!response.ok) throw new ArtifactError(`Unit Cell 预览失败：HTTP ${response.status}`)
  const payload = await response.json() as FabricInstancePreview
  if (payload.schema_version !== '1.0' || payload.kind !== 'fabric_instance_preview'
    || payload.manufacturing_result_id !== resultId || payload.manufacturing_status !== 'preview_only_not_in_stl'
    || !Number.isInteger(payload.count) || payload.count < 0 || payload.count > 10000
    || !Array.isArray(payload.instances) || payload.instances.length !== payload.count
    || !Array.isArray(payload.prototype?.vertices) || !Array.isArray(payload.prototype?.faces)) {
    throw new ArtifactError('Unit Cell 预览数据与当前制造结果不匹配。')
  }
  return payload
}

async function fetchArtifact(resultId: string, suffix: 'preview.glb' | 'model.stl', signal?: AbortSignal,
  fetcher: typeof fetch = fetch): Promise<Response> {
  if (!resultId) throw new ArtifactError('没有当前有效的制造结果，请重新检查并生成。')
  let response: Response
  try {
    response = await fetcher(`${apiBaseUrl()}/api/v1/manufacturing/${encodeURIComponent(resultId)}/${suffix}`,
      { method: 'GET', signal })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ArtifactError('无法连接制造服务，请检查后端连接。')
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const detail = payload && typeof payload === 'object' && 'message' in payload
      ? String(payload.message) : `HTTP ${response.status}`
    throw new ArtifactError(`${suffix === 'model.stl' ? 'STL 下载' : '三维预览'}失败：${detail}`)
  }
  return response
}

export async function fetchPreviewGlb(resultId: string, signal?: AbortSignal, fetcher: typeof fetch = fetch) {
  const response = await fetchArtifact(resultId, 'preview.glb', signal, fetcher)
  const data = await response.arrayBuffer()
  const header = new DataView(data)
  if (data.byteLength < 20 || header.getUint32(0, true) !== 0x46546c67) {
    throw new ArtifactError('后端返回的三维预览不是有效 GLB。')
  }
  return data
}

export async function fetchStl(resultId: string, signal?: AbortSignal, fetcher: typeof fetch = fetch) {
  const response = await fetchArtifact(resultId, 'model.stl', signal, fetcher)
  const bytes = await response.arrayBuffer()
  if (bytes.byteLength < 84) throw new ArtifactError('后端返回的 STL 文件无效。')
  return new Blob([bytes], { type: 'model/stl' })
}

export function stlFileName(projectName: string | null): string {
  const name = (projectName ?? 'xiaomang-pattern').replace(/\.(pattern\.json|json|png|jpe?g|svg)$/i, '')
    .replace(/[\\/:*?"<>|\x00-\x1f]/g, '_').trim().replace(/[. ]+$/, '')
  return `${name || 'xiaomang-pattern'}.stl`
}
