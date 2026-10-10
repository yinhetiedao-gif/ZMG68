import { describe, it, expect } from 'vitest'
import { centerHeightField, setCenterFabricHeight } from './fabricModifiers'
import { applyFabricHeightRecipe } from './fabricPresets'
import { setOriginalShape } from './fabricOriginal'
import { restoreSnapshot } from './editor'
import { saveDraft, loadDraft } from '../draft/localDraft'
import { phase1aDocument, phase1aCatalog as catalog } from '../test/phase1aFixture'

const bounds = { min_x: 10, min_y: 20, max_x: 70, max_y: 60, width: 60, height: 40, units: 'mm' as const }
describe('Center recipe uses radius-zero Ring and the existing ownership graph', () => {
  it.each(['original', 'unit_cell'])('one commit preserves %s shape and every non-height choice', source => {
    let dto = phase1aDocument()
    dto.document.canvas = { width: 120, height: 80, origin_x: 20, origin_y: 40, unit: 'svg', mm_per_unit: .5 }
    if (source === 'original') dto = setOriginalShape(dto, catalog, { size_scale: 1.2 })
    const cfg = dto.document.metadata.fabric_config as any
    cfg.output_mode = 'cells_only'; cfg.base.type = 'grid'; cfg.placement.mode = 'area_fill'
    cfg.field_modifiers = { scale: { enabled: true, field_id: 'user-ring', min_scale: .8, max_scale: 1.2 } }
    dto.document.fields.push({ id: 'user-ring', type: 'ring', parameters: { radius: 21 } })
    const before = structuredClone(dto)
    const next = applyFabricHeightRecipe(dto, catalog, bounds, 'center', 2), field = centerHeightField(next)!
    expect(next.document_revision).toBe(dto.document_revision + 1)
    expect(field.id).not.toBe('user-ring')
    expect(field.parameters).toEqual({ center_x: 40, center_y: 40, radius: 0, ring_width: Math.hypot(60, 40), falloff: 1, invert: false })
    const { field_modifiers, ...other } = next.document.metadata.fabric_config as any
    const { field_modifiers: previous, ...original } = before.document.metadata.fabric_config as any
    expect(other).toEqual(original); expect(field_modifiers.scale).toEqual(previous.scale)
    expect(next.document.elements).toBe(dto.document.elements); expect(next.document.modifiers).toBe(dto.document.modifiers)
    expect(next.document.fields[0]).toEqual(before.document.fields[0]); expect(dto).toEqual(before)
  })
  it.each(['modifier', 'fabric', 'composite', 'legacy'])('isolates a center field shared by %s', kind => {
    const dto = applyFabricHeightRecipe(phase1aDocument(), catalog, bounds, 'center', 2)
    const field = centerHeightField(dto)!, snapshot = structuredClone(field)
    if (kind === 'modifier') dto.document.modifiers.push({ id: 'size-user', field_id: field.id })
    if (kind === 'fabric') (dto.document.metadata.fabric_config as any).field_modifiers.orientation = { enabled: false, field_id: field.id }
    if (kind === 'composite') dto.document.fields.push({ id: 'comp', type: 'composite', parameters: { input_a_field_id: field.id } })
    if (kind === 'legacy') dto.document.metadata.legacy = { field_id: field.id }
    const next = setCenterFabricHeight(dto, catalog, bounds, { center_x: 31, range_mm: 12 })
    expect(centerHeightField(next)!.id).not.toBe(field.id)
    expect(next.document.fields.find(f => f.id === field.id)).toEqual(snapshot)
    expect((next.document.metadata.web_fabric_recipe as any).field_id).toBe(centerHeightField(next)!.id)
    expect(setCenterFabricHeight(next, catalog, bounds, { center_y: 29 }).document.fields).toHaveLength(next.document.fields.length)
  })
  it('defaults are stable after bounds changes; Reset/Undo/Redo/draft restore the entire graph', async () => {
    const first = applyFabricHeightRecipe(phase1aDocument(), catalog, bounds, 'center', 2)
    const movedBounds = { ...bounds, min_x: 100, max_x: 160 }
    const edited = setCenterFabricHeight(first, catalog, movedBounds, { center_x: 31, range_mm: 12, max_height_mm: 8 })
    expect((centerHeightField(edited)!.parameters as any).center_y).toBe(40)
    const reset = applyFabricHeightRecipe(edited, catalog, movedBounds, 'center', 2)
    expect(reset.document).toEqual(first.document)
    expect(reset.document_revision).toBe(edited.document_revision + 1)
    expect(restoreSnapshot(edited, reset.document_revision).document).toEqual(edited.document)
    expect(restoreSnapshot(reset, edited.document_revision + 2).document).toEqual(reset.document)
    await saveDraft(edited, 'center recipe', null)
    expect((await loadDraft())!.dto).toEqual(edited)
    expect(setCenterFabricHeight((await loadDraft())!.dto, catalog, bounds, { range_mm: 15 }).document.fields).toHaveLength(1)
  })
  it.each(['original', 'unit_cell'])('three recipes switch without replacement or duplicate bindings in %s', source => {
    let dto = phase1aDocument()
    if (source === 'original') dto = setOriginalShape(dto, catalog, { size_scale: 1.1 })
    const cfg = structuredClone(dto.document.metadata.fabric_config) as any
    const ids: Record<string, string> = {}
    for (const kind of ['directional', 'wave', 'center', 'directional', 'center'] as const) {
      dto = applyFabricHeightRecipe(dto, catalog, bounds, kind, 2)
      const next = dto.document.metadata.fabric_config as any
      expect(next.unit_cell).toEqual(cfg.unit_cell); expect(next.original_shape).toEqual(cfg.original_shape)
      expect(next.base).toEqual(cfg.base); expect(next.placement).toEqual(cfg.placement)
      expect(next.output_mode).toBe(cfg.output_mode)
      const id = next.field_modifiers.height.field_id
      if (ids[kind]) expect(id).toBe(ids[kind]); ids[kind] = id
    }
    expect(dto.document.fields).toHaveLength(3)
  })
  it('rejects non-finite/zero support and invalid height without mutation', () => {
    const dto = phase1aDocument(), before = structuredClone(dto)
    for (const edits of [{ range_mm: 0 }, { range_mm: -1 }, { center_x: NaN }, { range_mm: Infinity }, { min_height_mm: 8, max_height_mm: 2 }])
      expect(() => setCenterFabricHeight(dto, catalog, bounds, edits)).toThrow()
    expect(dto).toEqual(before)
  })
})
