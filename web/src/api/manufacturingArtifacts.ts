import { apiBaseUrl } from './client'

export class ArtifactError extends Error {}

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
