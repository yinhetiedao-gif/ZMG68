import { describe, expect, it, vi } from 'vitest'
import { importImage, ImageImportError } from './import'

function reply(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status,
    json: async () => value } as Response
}

describe('WM5.5 image upload boundary', () => {
  it('uploads bytes, imports by opaque ID and never parses SVG in React', async () => {
    const dto = { schema_version: '1.0', document_id: 'opaque-id', document_revision: 0,
      document: { elements: [{ id: 'dot-1', type: 'circle' }] }, assets: [] }
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(reply({ asset_id: 'opaque-id', media_type: 'image/png', filename: 'dots.png' }))
      .mockResolvedValueOnce(reply(dto))
    const file = new File(['PNG DATA'], 'dots.png', { type: 'image/png' })
    expect(await importImage(file, fetcher)).toEqual(dto)
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(fetcher.mock.calls[0][0]).toMatch(/\/api\/v1\/assets$/)
    expect(fetcher.mock.calls[0][1]?.body).toBe(file)
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toEqual({ asset_id: 'opaque-id' })
  })

  it('rejects invalid files before transfer and reports backend failure', async () => {
    const fetcher = vi.fn<typeof fetch>()
    await expect(importImage(new File(['x'], 'x.txt'), fetcher)).rejects.toThrow(ImageImportError)
    await expect(importImage(new File([], 'empty.svg'), fetcher)).rejects.toThrow(/为空/)
    expect(fetcher).not.toHaveBeenCalled()
    fetcher.mockResolvedValue(reply({ message: 'SVG 内容无效。' }, 422))
    await expect(importImage(new File(['bad'], 'bad.svg'), fetcher)).rejects.toThrow(/SVG 内容无效/)
  })
})
