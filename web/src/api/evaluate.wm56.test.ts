import { describe, expect, it, vi } from 'vitest'
import { evaluateDocument } from './evaluate'
import type { PatternDocumentDTO } from '../model/types'

const dto = { schema_version: '1.0', document_id: 'fixture', document_revision: 1,
  document: { schema_version: 1, canvas: { width: 20, height: 20, unit: 'mm', mm_per_unit: 1 },
    reference: {}, elements: [], groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [] },
  assets: [],
} satisfies PatternDocumentDTO

const dot = { id: 'dot', type: 'circle', x: 10, y: 10, width: 4, height: 4,
  rotation: 0, units: 'mm' }

function mockResponse(geometry: unknown[]) {
  return vi.fn<typeof fetch>(async () => ({ ok: true, json: async () => ({
    schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
    geometry, bounds_mm: null, warnings: [],
  }) } as Response))
}

describe('WM5.6 Evaluate renderability boundary', () => {
  it('rejects non-positive dimensions before replacing the last valid frame', async () => {
    await expect(evaluateDocument(dto, undefined, mockResponse([{ ...dot, width: 0 }]))).rejects.toThrow('不匹配')
    await expect(evaluateDocument(dto, undefined, mockResponse([{ ...dot, height: -1 }]))).rejects.toThrow('不匹配')
  })

  it('rejects duplicate final IDs before React creates unstable sibling keys', async () => {
    await expect(evaluateDocument(dto, undefined, mockResponse([dot, { ...dot, x: 14 }]))).rejects.toThrow('不匹配')
  })

  it('accepts distinct stable final IDs', async () => {
    const result = await evaluateDocument(dto, undefined, mockResponse([dot, { ...dot, id: 'dot:derived-2' }]))
    expect(result.geometry.map((item) => item.id)).toEqual(['dot', 'dot:derived-2'])
  })
})
