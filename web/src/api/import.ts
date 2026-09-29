import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'

export class ImageImportError extends Error {}

const mediaTypes: Record<string, string> = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', svg: 'image/svg+xml',
}

async function message(response: Response): Promise<string> {
  const payload: unknown = await response.json().catch(() => null)
  if (payload && typeof payload === 'object' && 'message' in payload) return String(payload.message)
  return `HTTP ${response.status}`
}

/** Transport only: Python owns preprocessing, vectorization and SVG normalization. */
export async function importImage(file: File, fetcher: typeof fetch = fetch): Promise<PatternDocumentDTO> {
  const suffix = file.name.split('.').pop()?.toLowerCase() ?? ''
  const mediaType = mediaTypes[suffix]
  if (!mediaType) throw new ImageImportError('仅支持 PNG、JPG/JPEG 和 SVG 文件。')
  if (!file.size || file.size > 8 * 1024 * 1024) throw new ImageImportError('文件为空或超过 8 MiB。')
  let uploaded: Response
  try {
    uploaded = await fetcher(`${apiBaseUrl()}/api/v1/assets`, {
      method: 'POST', headers: { 'Content-Type': mediaType, 'X-Filename': encodeURIComponent(file.name) },
      body: file,
    })
  } catch {
    throw new ImageImportError('无法连接图片上传服务。')
  }
  if (!uploaded.ok) throw new ImageImportError(await message(uploaded))
  const asset: unknown = await uploaded.json().catch(() => null)
  if (!asset || typeof asset !== 'object' || !('asset_id' in asset) || typeof asset.asset_id !== 'string') {
    throw new ImageImportError('上传结果缺少资产 ID。')
  }
  let imported: Response
  try {
    imported = await fetcher(`${apiBaseUrl()}/api/v1/import`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id: asset.asset_id }),
    })
  } catch {
    throw new ImageImportError('无法连接图片转换服务。')
  }
  if (!imported.ok) throw new ImageImportError(await message(imported))
  const dto: unknown = await imported.json().catch(() => null)
  if (!dto || typeof dto !== 'object' || !('schema_version' in dto) || dto.schema_version !== '1.0'
      || !('document' in dto) || !dto.document || typeof dto.document !== 'object'
      || !('elements' in dto.document) || !Array.isArray(dto.document.elements)) {
    throw new ImageImportError('图片转换结果不是有效的 PatternDocument。')
  }
  return dto as PatternDocumentDTO
}
