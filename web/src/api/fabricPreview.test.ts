import { describe, expect, it, vi } from 'vitest'
import { requestFabricPreview } from './fabricPreview'
import type { PatternDocumentDTO } from '../model/types'

const dto = { schema_version: '1.0', document_id: 'fabric', document_revision: 3,
  document: { metadata: { fabric_config: {} }, elements: [] }, assets: [] } as unknown as PatternDocumentDTO

describe('Fabric design preview API', () => {
  it('uses a distinct preview route and rejects mismatched revisions', async () => {
    const response = { kind: 'fabric_instance_preview', document_id: 'fabric', document_revision: 3,
      count: 0, active_count: 0, total_count: 0, instances: [], base_preview: { bounds_mm: [0, 0, 10, 10] } }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue({ ok: true,
      json: async () => response } as Response)
    expect((await requestFabricPreview(dto, undefined, fetcher)).total_count).toBe(0)
    expect(String(fetcher.mock.calls[0][0])).toContain('/api/v1/fabric/preview')
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body)).document_revision).toBe(3)
    fetcher.mockResolvedValueOnce({ ok: true, json: async () => ({ ...response, document_revision: 2 }) } as Response)
    await expect(requestFabricPreview(dto, undefined, fetcher)).rejects.toThrow('请求 fabric / revision 3，响应 fabric / revision 2')
    fetcher.mockResolvedValueOnce({ ok: true, json: async () => ({ ...response, count: 1,
      total_count: 1, instances: [{ x_mm: 1, y_mm: 2, rotation_deg: 0 }] }) } as Response)
    await expect(requestFabricPreview(dto, undefined, fetcher)).rejects.toThrow('格式过旧')
  })
})
