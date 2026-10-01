import { describe, expect, it, vi } from 'vitest'
import { fetchFabricPlan } from './manufacturingArtifacts'

describe('F2 instance-preview artifact', () => {
  it('accepts matching plans, rejects wrong result IDs, and treats legacy 204 as no plan', async () => {
    const payload = { schema_version: '1.0', kind: 'fabric_instance_preview', manufacturing_result_id: 'mfg-1',
      cell_type: 'cylinder', count: 1, prototype: { vertices: [[0, 0, 0]], faces: [[0, 0, 0]] },
      instances: [{ id: 'fabric:r0:c0', x_mm: 1, y_mm: 1, z_mm: .6, rotation_deg: 0, scale: 1 }],
      manufacturing_status: 'preview_only_not_in_stl' }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue({ ok: true, status: 200,
      json: async () => payload } as Response)
    expect((await fetchFabricPlan('mfg-1', undefined, fetcher))?.count).toBe(1)
    expect(String(fetcher.mock.calls[0][0])).toContain('/mfg-1/fabric-plan')
    await expect(fetchFabricPlan('mfg-2', undefined, fetcher)).rejects.toThrow('不匹配')
    fetcher.mockResolvedValueOnce({ status: 204 } as Response)
    expect(await fetchFabricPlan('legacy', undefined, fetcher)).toBeNull()
  })
})
