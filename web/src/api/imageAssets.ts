import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'
import type { SourceAssetDraft } from '../draft/localDraft'

export type ImageSources = Record<string, SourceAssetDraft>

/** Transport rebinding only. The stable browser asset token and design revision
 * never change when a temporary server asset expires. No raster math here. */
export function imageAssetFetcher(getSources: () => ImageSources, fetcher: typeof fetch = fetch): typeof fetch {
  const uploads = new Map<string, Promise<string>>()
  const upload = (token: string, signal?: AbortSignal | null): Promise<string> => {
    const source = getSources()[token]
    if (!source || !source.blob.size || source.blob.size > 8 * 1024 * 1024 ||
        !['image/png', 'image/jpeg'].includes(source.media_type))
      return Promise.reject(new Error('图片场源图片未保存，请重新选择 PNG/JPG。'))
    let pending = uploads.get(token)
    if (!pending) {
      // Shared upload must not be cancelled by one obsolete evaluate request.
      pending = fetcher(`${apiBaseUrl()}/api/v1/assets`, {
        method: 'POST', headers: { 'Content-Type': source.media_type, 'X-Filename': encodeURIComponent(source.filename) },
        body: source.blob,
      }).then(async (response) => {
        const body = await response.json()
        if (!response.ok || typeof body.asset_id !== 'string') throw new Error(body.message ?? '图片场上传失败。')
        return body.asset_id as string
      }).catch((error) => { uploads.delete(token); throw error })
      uploads.set(token, pending)
    }
    return pending.then((id) => { signal?.throwIfAborted(); return id })
  }
  return async (input, init) => {
    if (typeof init?.body !== 'string') return fetcher(input, init)
    const body = JSON.parse(init.body) as { document?: PatternDocumentDTO }
    const dto = body.document
    const images = dto?.assets.filter((asset) => asset.role.startsWith('field:')) ?? []
    if (!dto || !images.length) return fetcher(input, init)
    const send = async () => {
      const assets = await Promise.all(dto.assets.map(async (asset) => asset.role.startsWith('field:')
        ? { ...asset, asset_id: await upload(asset.asset_id, init.signal) } : asset))
      init.signal?.throwIfAborted()
      return fetcher(input, { ...init, body: JSON.stringify({ ...body, document: { ...dto, assets } }) })
    }
    let response = await send()
    const error = !response.ok ? await response.clone().json().catch(() => null) : null
    if (error?.code === 'unresolved_asset') {
      images.forEach((asset) => uploads.delete(asset.asset_id))
      response = await send() // one recovery attempt; retain real errors
    }
    return response
  }
}

export function bindImageSource(dto: PatternDocumentDTO, fieldId: string, token: string,
  mediaType: string, increment = true): PatternDocumentDTO {
  if (!dto.document.fields.some((field) => field.id === fieldId && ['image', 'distance'].includes(String(field.type))))
    throw new Error('图片场不存在。')
  if (!['image/png', 'image/jpeg'].includes(mediaType)) throw new Error('图片场只支持 PNG/JPG，不支持 SVG。')
  return { ...dto, document_revision: dto.document_revision + (increment ? 1 : 0), assets: [
    ...dto.assets.filter((asset) => asset.role !== `field:${fieldId}`),
    { role: `field:${fieldId}`, asset_id: token, media_type: mediaType },
  ] }
}
