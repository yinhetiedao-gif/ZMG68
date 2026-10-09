import { describe, it, expect } from 'vitest'
import { directionalHeightField, setDirectionalFabricHeight, setUniformFabricHeight, fabricFieldModifier } from './fabricModifiers'
import { applyDirectionalFabricRecipe } from './fabricPresets'
import { restoreSnapshot } from './editor'
import { saveDraft, loadDraft } from '../draft/localDraft'
import { phase1aDocument, phase1aCatalog as catalog, phase1aBounds as bounds } from '../test/phase1aFixture'

describe('Phase 1A owned height and complete recipe', () => {
  it('uniform never creates a field; directional is one revision and never borrows a user field', () => {
    const dto = phase1aDocument()
    expect(setUniformFabricHeight(dto, catalog)).toBe(dto)
    dto.document.fields.push({ id: 'user-linear', type: 'linear', parameters: { angle: 80, start: 1, end: 9 } })
    dto.document.modifiers.push({ id: 'user-size', field_id: 'user-linear' })
    const original = JSON.stringify(dto)
    const next = setDirectionalFabricHeight(dto, catalog, bounds)
    expect(next.document_revision).toBe(4)
    expect(next.document.fields[0]).toEqual(dto.document.fields[0])
    expect(directionalHeightField(next)?.id).not.toBe('user-linear')
    expect(directionalHeightField(next)?.parameters).toEqual({ angle: 0, start: 10, end: 70 })
    expect(setDirectionalFabricHeight(next, catalog, bounds).document.fields).toHaveLength(2)
    expect(restoreSnapshot(dto, next.document_revision).document).toEqual(dto.document)
    expect(JSON.stringify(dto)).toBe(original)
  })
  it.each(['modifier', 'fabric', 'composite', 'legacy'])('isolates an owned field shared with %s', kind => {
    const next = setDirectionalFabricHeight(phase1aDocument(), catalog, bounds)
    const field = directionalHeightField(next)!
    if (kind === 'modifier') next.document.modifiers.push({ field_id: field.id })
    if (kind === 'fabric') (next.document.metadata.fabric_config as any).field_modifiers.scale = { enabled: false, field_id: field.id }
    if (kind === 'composite') next.document.fields.push({ id: 'combine', type: 'composite', parameters: { input_a_field_id: field.id } })
    if (kind === 'legacy') next.document.metadata.legacy = { modifiers: [{ field_id: field.id }] }
    const before = structuredClone(field)
    const edited = setDirectionalFabricHeight(next, catalog, bounds, { angle: 45 })
    expect(directionalHeightField(edited)?.id).not.toBe(field.id)
    expect(edited.document.fields.find(item => item.id === field.id)).toEqual(before)
    expect(setDirectionalFabricHeight(edited, catalog, bounds, { angle: 90 }).document.fields.length).toBe(edited.document.fields.length)
    expect(setUniformFabricHeight(edited, catalog).document.fields).toEqual(edited.document.fields)
  })
  it('uniform preserves scale/density/orientation bindings and fields', () => {
    const dto = setDirectionalFabricHeight(phase1aDocument(), catalog, bounds)
    const modifiers = (dto.document.metadata.fabric_config as any).field_modifiers
    modifiers.scale = { enabled: true, field_id: 'unrelated', min_scale: .5, max_scale: 2 }
    const next = setUniformFabricHeight(dto, catalog)
    expect(next.document_revision).toBe(dto.document_revision + 1)
    expect(fabricFieldModifier(next, 'height')?.enabled).toBe(false)
    expect(fabricFieldModifier(next, 'scale')).toBe(modifiers.scale)
    expect(next.document.fields).toBe(dto.document.fields)
  })
  it('uses registered world-mm bounds, preserves assets, and refuses an unmapped pixel project', () => {
    const dto = phase1aDocument()
    dto.document.canvas = { width: 60, height: 40, origin_x: 10, origin_y: 20, unit: 'px', mm_per_unit: .25 }
    dto.assets = [{ role: 'field:source', asset_id: 'browser-blob', media_type: 'image/png' }]
    const next = setDirectionalFabricHeight(dto, catalog,
      { min_x: 2.5, min_y: 5, max_x: 17.5, max_y: 15, width: 15, height: 10, units: 'mm' })
    expect(directionalHeightField(next)?.parameters).toEqual({ angle: 0, start: 2.5, end: 17.5 })
    expect(next.assets).toBe(dto.assets)
    dto.document.canvas.mm_per_unit = null
    expect(() => setDirectionalFabricHeight(dto, catalog, null)).toThrow('世界毫米比例')
  })
  it('recipe/reset preserve source/layout/unknown metadata, and draft restores the full graph', async () => {
    const dto = phase1aDocument()
    dto.document.metadata.custom = { keep: true }
    dto.document.metadata.layout = { rows: 4 }
    ;(dto.document.metadata.fabric_config as any).custom_fabric = 'keep'
    const initial = applyDirectionalFabricRecipe(dto, catalog, bounds)
    const edited = setDirectionalFabricHeight(initial, catalog, bounds, { angle: 90, max_height_mm: 8 })
    const reset = applyDirectionalFabricRecipe(edited, catalog, bounds)
    expect(reset.document_revision).toBe(edited.document_revision + 1)
    expect(reset.document.fields).toEqual(initial.document.fields)
    expect(reset.document.metadata.fabric_config).toEqual(initial.document.metadata.fabric_config)
    expect(reset.document.elements).toBe(dto.document.elements)
    expect(reset.document.metadata.layout).toBe(dto.document.metadata.layout)
    expect(reset.document.metadata.custom).toBe(dto.document.metadata.custom)
    expect(restoreSnapshot(edited, reset.document_revision).document).toEqual(edited.document)
    await saveDraft(reset, 'recipe', null)
    expect((await loadDraft())?.dto).toEqual(reset)
    expect(() => setDirectionalFabricHeight(reset, catalog, bounds, { min_height_mm: 9, max_height_mm: 3 })).toThrow()
  })
})
