import { describe, it, expect } from 'vitest'
import { setDirectionalFabricHeight, directionalHeightField, waveHeightField, setWaveFabricHeight, setUniformFabricHeight } from './fabricModifiers'
import { applyWaveFabricRecipe, waveFabricRecipe } from './fabricPresets'
import { restoreSnapshot } from './editor'
import { saveDraft, loadDraft } from '../draft/localDraft'
import { phase1aDocument, phase1aCatalog as catalog, phase1aBounds } from '../test/phase1aFixture'

describe('Wave recipe uses existing height ownership and normal document storage', () => {
  it('one revision, complete parameters, no user-field borrowing and no source/layout changes', () => {
    const dto = phase1aDocument(), original = structuredClone(dto)
    dto.document.fields.push({ id: 'user-wave', type: 'wave', parameters: { wavelength: 87, angle: 81 } })
    dto.document.metadata.layout = { rows: 8 }
    const config = dto.document.metadata.fabric_config as any
    config.output_mode = 'cells_only'
    config.base = { type: 'grid', thickness_mm: 1, spacing_x_mm: 8, spacing_y_mm: 8, line_width_mm: 1, margin_mm: 2 }
    config.field_modifiers = { scale: { enabled: true, field_id: 'user-wave', min_scale: .8, max_scale: 1.2 } }
    const before = structuredClone(dto)
    const next = applyWaveFabricRecipe(dto, catalog), field = waveHeightField(next)!
    expect(next.document_revision).toBe(dto.document_revision + 1)
    expect(field.id).not.toBe('user-wave')
    expect(field.parameters).toEqual(waveFabricRecipe.field.parameters)
    expect(next.document.fields[0]).toEqual(dto.document.fields[0])
    expect(next.document.elements).toBe(dto.document.elements)
    expect(next.document.transforms).toBe(dto.document.transforms)
    expect(next.document.metadata.layout).toBe(dto.document.metadata.layout)
    const applied = next.document.metadata.fabric_config as any
    expect(applied.base).toEqual(config.base); expect(applied.output_mode).toBe('cells_only')
    expect(applied.field_modifiers.scale).toEqual(config.field_modifiers.scale)
    expect(applied.placement.mode).toBe('pattern_points')
    expect(applied.unit_cell.width_mm).toBe(4.8)
    expect(next.document.metadata.web_fabric_recipe).toMatchObject({ id: 'wave-height', version: 1, units: 'mm', field_id: field.id })
    expect(dto).toEqual(before)
    expect(original.document.fields).toHaveLength(0)
  })
  it.each(['modifier', 'fabric', 'composite', 'legacy'])('copy-isolates a wave shared by %s without touching its user', kind => {
    const dto = applyWaveFabricRecipe(phase1aDocument(), catalog), field = waveHeightField(dto)!
    const snapshot = structuredClone(field)
    if (kind === 'modifier') dto.document.modifiers.push({ id: 'size', field_id: field.id })
    if (kind === 'fabric') (dto.document.metadata.fabric_config as any).field_modifiers.orientation = { enabled: false, field_id: field.id }
    if (kind === 'composite') dto.document.fields.push({ id: 'other', type: 'composite', parameters: { input_a_field_id: field.id } })
    if (kind === 'legacy') dto.document.metadata.legacy = { field_id: field.id }
    const edited = setWaveFabricHeight(dto, catalog, { wavelength: 90 })
    expect(waveHeightField(edited)?.id).not.toBe(field.id)
    expect(edited.document.fields.find(f => f.id === field.id)).toEqual(snapshot)
    expect((edited.document.metadata.web_fabric_recipe as any).field_id).toBe(waveHeightField(edited)?.id)
    expect(setWaveFabricHeight(edited, catalog, { angle: 45 }).document.fields).toHaveLength(edited.document.fields.length)
  })
  it('direction/wave/uniform switching reuses each owned ID, including the old version-1 owner', () => {
    let dto = setDirectionalFabricHeight(phase1aDocument(), catalog, phase1aBounds)
    const linearId = directionalHeightField(dto)!.id
    dto.document.metadata.web_fabric_height_effect = { version: 1, field_id: linearId }
    dto = applyWaveFabricRecipe(dto, catalog)
    const waveId = waveHeightField(dto)!.id
    dto = setUniformFabricHeight(dto, catalog)
    dto = setDirectionalFabricHeight(dto, catalog, phase1aBounds, { angle: 45 })
    expect(directionalHeightField(dto)?.id).toBe(linearId)
    dto = setWaveFabricHeight(dto, catalog, { angle: 90 })
    expect(waveHeightField(dto)?.id).toBe(waveId)
    expect(dto.document.fields).toHaveLength(2)
  })
  it('Reset/Undo/Redo and IndexedDB retain the complete graph and explicit output choice', async () => {
    const dto = phase1aDocument()
    ;(dto.document.metadata.fabric_config as any).output_mode = 'cells_with_base'
    const first = applyWaveFabricRecipe(dto, catalog)
    const edited = setWaveFabricHeight(first, catalog, { angle: 45, wavelength: 120, phase: 1, invert: true, max_height_mm: 8 })
    expect((edited.document.metadata.web_fabric_recipe as any).field_parameters).toEqual(waveHeightField(edited)?.parameters)
    const reset = applyWaveFabricRecipe(edited, catalog)
    expect(reset.document_revision).toBe(edited.document_revision + 1)
    expect(reset.document).toEqual(first.document)
    const undo = restoreSnapshot(edited, reset.document_revision)
    expect(undo.document).toEqual(edited.document)
    expect(restoreSnapshot(reset, undo.document_revision).document).toEqual(reset.document)
    await saveDraft(edited, 'wave recipe', null)
    const restored = (await loadDraft())!.dto
    expect(restored).toEqual(edited)
    expect(setWaveFabricHeight(restored, catalog, { wavelength: 36 }).document.fields).toHaveLength(1)
  })
  it('preserves legacy with-base semantics and defaults only new Fabric to cells-only', () => {
    const legacy = applyWaveFabricRecipe(phase1aDocument(), catalog)
    expect((legacy.document.metadata.fabric_config as any).output_mode).toBe('cells_with_base')
    const fresh = phase1aDocument(); delete fresh.document.metadata.fabric_config
    expect((applyWaveFabricRecipe(fresh, catalog).document.metadata.fabric_config as any).output_mode).toBe('cells_only')
  })
  it('world-mm wavelength is not scaled again; invalid wavelength/height cannot replace a valid design', () => {
    const dto = phase1aDocument()
    dto.document.canvas = { width: 120, height: 80, origin_x: 20, origin_y: 40, unit: 'svg', mm_per_unit: .5 }
    const next = setWaveFabricHeight(dto, catalog, { wavelength: 36 })
    expect((waveHeightField(next)?.parameters as any).wavelength).toBe(36)
    expect(next.document.canvas).toBe(dto.document.canvas)
    expect(() => setWaveFabricHeight(next, catalog, { wavelength: 0 })).toThrow()
    expect(() => setWaveFabricHeight(next, catalog, { min_height_mm: 9, max_height_mm: 2 })).toThrow()
    expect(() => setWaveFabricHeight(next, catalog, { angle: NaN })).toThrow()
  })
})
