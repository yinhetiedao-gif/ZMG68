import { describe, expect, it } from 'vitest'
import { phase1aDocument, phase1aCatalog } from '../test/phase1aFixture'
import { setOriginalShape } from '../document/fabricOriginal'
import { temporaryFabricDimensions } from './fabricTemporaryDimensions'
import type { FabricDesignPreview } from '../api/fabricPreview'

describe('display-only Fabric dimensions', () => {
  it('original contour drafts change only local size/uniform height, preserving holes/prototypes and anchors without a commit', () => {
    const dto = setOriginalShape(phase1aDocument(), phase1aCatalog, { size_scale: 1.2, height_mm: 2 })
    const plan = { shape_source: 'original', contour_prototypes: { outline: {vertices:[[0,0,0]],faces:[]} }, instances:[{
      id:'outline',x_mm:21,y_mm:34,z_mm:0,rotation_deg:0,enabled:true,cell_width_mm:9,cell_depth_mm:4.5,height_mm:2,cell_height_mm:2,
    }] } as unknown as FabricDesignPreview
    const before = structuredClone(dto)
    const draft = temporaryFabricDimensions(plan,dto,dto,{original_size_scale:1.8,height_mm:3})!
    expect(draft.instances[0]).toMatchObject({x_mm:21,y_mm:34,z_mm:0,rotation_deg:0,cell_width_mm:13.5,cell_depth_mm:6.75,height_mm:3})
    expect(draft.contour_prototypes).toBe(plan.contour_prototypes)
    expect(dto).toEqual(before)
    ;(dto.document.metadata.fabric_config as any).field_modifiers={height:{enabled:true}}
    expect(temporaryFabricDimensions(plan,dto,dto,{height_mm:9})).toBe(plan)
  })
  it.each([0, .6])('uses final dimensions once, preserves positions/rotation/relative size and Z=%s', z => {
    const dto = phase1aDocument()
    const plan = { instances: [{ x_mm: 30, y_mm: 40, z_mm: z, rotation_deg: 37, enabled: true,
      scale_x: 1.5, scale_y: .75, base_width_mm: 2, base_depth_mm: 2, base_height_mm: 3,
      cell_width_mm: 3.6, cell_depth_mm: 1.8, cell_height_mm: 3, height_mm: 3 }] } as FabricDesignPreview
    const original = structuredClone(plan)
    const next = temporaryFabricDimensions(plan, dto, dto, { uniform_size_mm: 4, height_mm: 6 })!
    expect(next.instances[0]).toMatchObject({ x_mm: 30, y_mm: 40, z_mm: z, rotation_deg: 37, enabled: true,
      cell_width_mm: 7.2, cell_depth_mm: 3.6, cell_height_mm: 6, height_mm: 6 })
    expect(plan).toEqual(original)
    expect(dto.document_revision).toBe(3)
    expect(temporaryFabricDimensions(plan, dto, dto, {})).toBe(plan)
  })
  it('never overrides height driven by a field, invalid inputs or another project', () => {
    const dto = phase1aDocument()
    ;(dto.document.metadata.fabric_config as any).field_modifiers = { height: { enabled: true } }
    const plan = { instances: [{ cell_width_mm: 2, cell_depth_mm: 2, height_mm: 8, cell_height_mm: 8 }] } as FabricDesignPreview
    expect(temporaryFabricDimensions(plan, dto, dto, { height_mm: 7 })).toBe(plan)
    expect(temporaryFabricDimensions(plan, dto, dto, { uniform_size_mm: NaN })).toBe(plan)
    expect(temporaryFabricDimensions(plan, dto, { ...dto, document_id: 'another' }, { uniform_size_mm: 4 })).toBe(plan)
  })
})
