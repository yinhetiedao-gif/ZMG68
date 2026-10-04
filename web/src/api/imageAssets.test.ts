import { describe, expect, it, vi } from 'vitest'
import { Blob as NodeBlob } from 'node:buffer'
import { bindImageSource, imageAssetFetcher } from './imageAssets'
import { createExampleDocument } from '../examples/catalog'
import { loadDraft, saveDraft, clearDraft } from '../draft/localDraft'

function project() {
  const dto = createExampleDocument('basic-grid', 'image-draft')
  dto.document.fields.push({ id: 'image', type: 'image', parameters: {
    image_path: '', black_is_one: true, sample_bounds: [0, 0, 60, 60] } })
  return bindImageSource(dto, 'image', 'browser-token', 'image/png')
}
const sources = () => ({ 'browser-token': { blob: new NodeBlob(['raster']) as Blob,
  filename: 'circle.png', media_type: 'image/png' } })
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const body = () => ({ method: 'POST', body: JSON.stringify({ document: project(), document_revision: 1 }) })

describe('ImageField asset lifecycle', () => {
  it('restores Distance Field with the same Blob/reupload path and unchanged revision', async () => {
    const dto = project()
    dto.document.fields[0].type = 'distance'
    dto.document.fields[0].parameters = { image_path: '', sample_bounds: [0, 0, 60, 60],
      threshold: .5, invert: false, auto_normalize: true, max_distance_mm: 10 }
    await saveDraft(dto, 'example', null, { pending_layout: null, example_session_active: false, image_sources: sources() })
    const restored = await loadDraft()
    expect(restored?.dto).toEqual(dto)
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ asset_id: 'expired' }))
      .mockResolvedValueOnce(response({ code: 'unresolved_asset' }, 422))
      .mockResolvedValueOnce(response({ asset_id: 'fresh' })).mockResolvedValueOnce(response({ ok: true }))
    const before = structuredClone(dto)
    const result = await imageAssetFetcher(() => restored!.image_sources!, fetcher)('/api/v1/fabric/preview', {
      method: 'POST', body: JSON.stringify({ document: bindImageSource(dto, 'image', 'browser-token', 'image/png', false) }) })
    expect(result.ok).toBe(true)
    expect(dto).toEqual(before)
    expect(fetcher).toHaveBeenCalledTimes(4)
    await clearDraft()
  })
  it('uploads once for repeated evaluate/preview requests without mutating the design or revision', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ asset_id: 'server-1' }))
      .mockResolvedValueOnce(response({ ok: true })).mockResolvedValueOnce(response({ ok: true }))
    const transport = imageAssetFetcher(sources, fetcher)
    const dto = project()
    const before = structuredClone(dto)
    await transport('/api/v1/evaluate', { method: 'POST', body: JSON.stringify({ document: dto }) })
    await transport('/api/v1/fabric/preview', { method: 'POST', body: JSON.stringify({ document: dto }) })
    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body)).document.assets[0].asset_id).toBe('server-1')
    expect(dto).toEqual(before)
    expect(JSON.parse(String(fetcher.mock.calls[2][1]?.body)).document.document_revision).toBe(dto.document_revision)
  })

  it('recovers after server restart or TTL expiration, then preserves the actual result/error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ asset_id: 'old' }))
      .mockResolvedValueOnce(response({ code: 'unresolved_asset' }, 422))
      .mockResolvedValueOnce(response({ asset_id: 'new' }))
      .mockResolvedValueOnce(response({ ok: true }))
    const result = await imageAssetFetcher(sources, fetcher)('/api/v1/fabric/preview', body())
    expect(result.ok).toBe(true)
    expect(JSON.parse(String(fetcher.mock.calls[3][1]?.body)).document.assets[0].asset_id).toBe('new')
    const failed = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ asset_id: 'a' }))
      .mockResolvedValueOnce(response({ code: 'unresolved_asset' }, 422))
      .mockResolvedValueOnce(response({ asset_id: 'b' }))
      .mockResolvedValueOnce(response({ code: 'unresolved_asset' }, 422))
    expect((await imageAssetFetcher(sources, failed)('/api/v1/evaluate', body())).status).toBe(422)
    expect(failed).toHaveBeenCalledTimes(4)
  })

  it('restores Blob and canonical image bindings through IndexedDB, with a fresh transport session', async () => {
    const dto = project()
    await saveDraft(dto, 'example', null, { pending_layout: null, example_session_active: false,
      image_sources: sources() })
    const restored = await loadDraft()
    expect(restored?.dto).toEqual(dto)
    expect(restored?.image_sources?.['browser-token'].blob.size).toBe(6)
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ asset_id: 'after-refresh' }))
      .mockResolvedValueOnce(response({ ok: true }))
    await imageAssetFetcher(() => restored!.image_sources!, fetcher)('/api/v1/evaluate', {
      method: 'POST', body: JSON.stringify({ document: restored!.dto }) })
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body)).document.assets[0].asset_id).toBe('after-refresh')
    await expect(saveDraft(dto, 'example', null)).rejects.toThrow(/源图片/)
    await clearDraft()
  })

  it('shares one in-flight upload between concurrent evaluate and preview', async () => {
    let finish!: (value: Response) => void
    const upload = new Promise<Response>(resolve => { finish = resolve })
    const fetcher = vi.fn<typeof fetch>().mockImplementation((input) =>
      String(input).endsWith('/assets') ? upload : Promise.resolve(response({ ok: true })))
    const transport = imageAssetFetcher(sources, fetcher)
    const evaluation = transport('/api/v1/evaluate', body())
    const preview = transport('/api/v1/fabric/preview', body())
    expect(fetcher).toHaveBeenCalledTimes(1)
    finish(response({ asset_id: 'shared' }))
    const results = await Promise.all([evaluation, preview])
    expect(results.every(result => result.ok)).toBe(true)
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it('discards aborts and rejects SVG or absent sources', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response({ asset_id: 'one' }))
    const transport = imageAssetFetcher(sources, fetcher)
    const controller = new AbortController(); controller.abort()
    await expect(transport('/api/v1/evaluate', { ...body(), signal: controller.signal })).rejects.toThrow()
    await expect(imageAssetFetcher(() => ({}), fetcher)('/api/v1/evaluate', body())).rejects.toThrow(/未保存/)
    expect(() => bindImageSource(project(), 'image', 'svg', 'image/svg+xml')).toThrow(/SVG/)
  })
})
