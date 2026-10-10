import { describe, expect, it, vi } from 'vitest'
import { requestFabricPreview } from './fabricPreview'
import type { PatternDocumentDTO } from '../model/types'

const dto = { schema_version: '1.0', document_id: 'fabric', document_revision: 3,
  document: { metadata: { fabric_config: {} }, elements: [] }, assets: [] } as unknown as PatternDocumentDTO

describe('Fabric design preview API', () => {
  it('original source requires each real contour prototype and does not accept an old shared-cell payload', async () => {
    const document=structuredClone(dto);document.document.metadata.fabric_config={shape_source:'original',output_mode:'cells_only'}
    const instance={id:'outline',x_mm:10,y_mm:20,z_mm:0,rotation_deg:0,enabled:true,scale_x:2,scale_y:3,scale:1,
      base_width_mm:1,base_depth_mm:1,base_height_mm:1,height_mm:2,cell_width_mm:2,cell_depth_mm:3,cell_height_mm:2}
    const payload={kind:'fabric_instance_preview',document_id:'fabric',document_revision:3,shape_source:'original',output_mode:'cells_only',
      unit_size_mode:'follow_pattern',count:1,active_count:1,total_count:1,instances:[instance],base_preview:{bounds_mm:[0,0,10,10]},
      contour_prototypes:{outline:{vertices:[[0,0,0],[1,0,0],[0,1,0]],faces:[[0,1,2]]}}}
    const fetcher=vi.fn<typeof fetch>().mockResolvedValue({ok:true,json:async()=>payload} as Response)
    expect((await requestFabricPreview(document,undefined,fetcher)).contour_prototypes).toEqual(payload.contour_prototypes)
    for(const bad of [{...payload,shape_source:'unit_cell'}, {...payload,contour_prototypes:{}},
      {...payload,contour_prototypes:{outline:{vertices:[[0,0,0]],faces:[[0,1,2]]}}}]){
      fetcher.mockResolvedValueOnce({ok:true,json:async()=>bad} as Response)
      await expect(requestFabricPreview(document,undefined,fetcher)).rejects.toThrow('格式过旧')
    }
  })
  it('uses a distinct preview route and rejects mismatched revisions', async () => {
    const response = { kind: 'fabric_instance_preview', document_id: 'fabric', document_revision: 3,
      unit_size_mode: 'follow_pattern',
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
