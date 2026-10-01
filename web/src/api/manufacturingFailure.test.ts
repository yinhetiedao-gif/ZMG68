import { describe, expect, it, vi } from 'vitest'
import { buildManufacturing } from './manufacturing'
import type { PatternDocumentDTO } from '../model/types'

const dto: PatternDocumentDTO = {
  schema_version: '1.0', document_id: 'test-design', document_revision: 3, assets: [],
  document: { schema_version: 1, canvas: { width: 20, height: 20, unit: 'mm', mm_per_unit: 1 },
    reference: {}, elements: [], groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [] },
}

describe('manufacturing failure diagnostics', () => {
  it('shows a development failure ID without exposing paths or a project-save action', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue({ ok: false, status: 422,
      json: async () => ({ code: 'manufacturing_validation_failed', message: 'Mesh 存在退化三角面',
        details: { failure_id: '20261001T120000000000Z-abc123' } }) } as Response)
    await expect(buildManufacturing(dto, 2, undefined, fetcher)).rejects.toThrow(
      'Mesh 存在退化三角面 · failure_id: 20261001T120000000000Z-abc123')
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('does not invent a failure ID when production response has none', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue({ ok: false, status: 422,
      json: async () => ({ code: 'manufacturing_validation_failed', message: '几何无效', details: null }) } as Response)
    await expect(buildManufacturing(dto, 2, undefined, fetcher)).rejects.toThrow(/^制造检查失败：几何无效$/)
  })
})
