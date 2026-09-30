import { describe, expect, it, vi } from 'vitest'
import { fetchPreviewGlb, fetchStl, stlFileName } from './manufacturingArtifacts'

function response(bytes: Uint8Array, status = 200): Response {
  return { ok: status === 200, status, arrayBuffer: async () => bytes.buffer,
    json: async () => ({ message: '制造结果已过期' }) } as Response
}

describe('P3 manufacturing artifact API', () => {
  it('requests preview and STL from the same encoded result ID', async () => {
    const glb = new Uint8Array(20)
    new DataView(glb.buffer).setUint32(0, 0x46546c67, true)
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response(glb))
      .mockResolvedValueOnce(response(new Uint8Array(100)))
    await fetchPreviewGlb('mesh/1', undefined, fetcher)
    expect((await fetchStl('mesh/1', undefined, fetcher)).size).toBe(100)
    expect(String(fetcher.mock.calls[0]?.[0])).toContain('/mesh%2F1/preview.glb')
    expect(String(fetcher.mock.calls[1]?.[0])).toContain('/mesh%2F1/model.stl')
  })

  it('rejects bad artifacts and makes safe project filenames', async () => {
    const bad = vi.fn<typeof fetch>().mockResolvedValue(response(new Uint8Array(10)))
    await expect(fetchPreviewGlb('id', undefined, bad)).rejects.toThrow('不是有效 GLB')
    await expect(fetchStl('id', undefined, bad)).rejects.toThrow('STL 文件无效')
    const gone = vi.fn<typeof fetch>().mockResolvedValue(response(new Uint8Array(), 404))
    await expect(fetchStl('id', undefined, gone)).rejects.toThrow('制造结果已过期')
    expect(stlFileName('我的图案.pattern.json')).toBe('我的图案.stl')
    expect(stlFileName('bad/name.png')).toBe('bad_name.stl')
  })
})
