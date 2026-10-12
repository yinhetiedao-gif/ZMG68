import { describe, expect, it } from 'vitest'
import { mkdirSync, writeFileSync } from 'node:fs'
import base from '../test/sizeFieldCatalog.json'
import design from '../test/designCatalog.json'
import { createExampleDocument } from '../examples/catalog'
import { createPatternPreset, openPatternPreset, patternPresetCandidate, changePatternPresetParameter, patternPresetControls, patternPresets } from './patternPresets'
import { dualOwner } from './presetDualBinding'
import { linearSizeOwner } from './linearSize'
import type { ParameterCatalog } from './parameterSchema'
const catalog = { ...base, definitions: { ...base.definitions, design } } as ParameterCatalog
const box = { min_x: 4.7, min_y: 5.85, max_x: 55.3, max_y: 54.15, width: 50.6, height: 48.3, units: 'mm' as const }
describe('P3 dedicated field has exactly two owned consumers', () => {
  it('digital weave creates the declared rectangle grid and a portable shared field', () => {
    const dto = createPatternPreset('digital-weave', 'preset-digital-weave', catalog)
    const pair = dualOwner(dto)!, owner = linearSizeOwner(dto)!
    expect(dto.document_revision).toBe(0)
    expect((dto.document.metadata['xiaomang_pattern_lab.parametric'] as any).grid).toMatchObject({ rows: 10, columns: 10,
      spacing_x: 5.2, spacing_y: 5.2, element_width: 3.8, element_height: 1.5, prototype: { kind: 'rect' } })
    expect(pair.rotation.field_id).toBe(owner.field.id)
    expect(pair.size.field_id).toBe(owner.field.id)
    expect(owner.field.parameters).toMatchObject({ cell_width: 5.2 })
    expect(Number((owner.field.parameters as any).offset_x)).toBeCloseTo(4, 12)
    expect(Number((owner.field.parameters as any).offset_y)).toBeCloseTo(4, 12)
    if (process.env.PATTERN_PRESET_EVIDENCE_DIR) {
      mkdirSync(process.env.PATTERN_PRESET_EVIDENCE_DIR, { recursive: true })
      writeFileSync(`${process.env.PATTERN_PRESET_EVIDENCE_DIR}/digital-weave.json`, JSON.stringify(dto, null, 2))
    }
  })
  it('repeat and Reset keep both IDs; external references force copy and simultaneous rebind', () => {
    let dto = createPatternPreset('digital-weave', 'repeat', catalog), pair = dualOwner(dto)!
    const ids = [pair.size.id, pair.rotation.id], field = linearSizeOwner(dto)!.field
    for (let i = 0; i < 3; i++) {
      dto = patternPresetCandidate(changePatternPresetParameter(openPatternPreset(dto, box, 'digital-weave', catalog), catalog, 'preset_cell_size', 7+i), catalog)
      expect(dto.document.fields).toHaveLength(1); expect(dto.document.modifiers).toHaveLength(2)
      expect([dualOwner(dto)!.size.id, dualOwner(dto)!.rotation.id]).toEqual(ids)
    }
    const originalField = structuredClone(dto.document.fields[0])
    dto.document.metadata.fabric_config = { field_modifiers: { height: { enabled: true, field_id: field.id } } }
    dto.document.modifiers.push({ id: 'user-rotation', type: 'rotation', enabled: true, field_id: field.id, mapping: { min_output: 3, max_output: 7 } })
    const candidate = patternPresetCandidate(openPatternPreset(dto, box, 'digital-weave', catalog, true), catalog)
    pair = dualOwner(candidate)!
    expect(pair.size.field_id).toBe(pair.rotation.field_id); expect(pair.size.field_id).not.toBe(field.id)
    expect(candidate.document.fields.find(f => f.id === field.id)).toEqual(originalField)
    expect(candidate.document.modifiers.at(-1)).toEqual(dto.document.modifiers.at(-1))
    expect(candidate.document.metadata.fabric_config).toEqual(dto.document.metadata.fabric_config)
    expect(pair.rotation.mapping).toMatchObject({ min_output: 0, max_output: 90, remap_curve: 'linear' })
  })
  it('switching back to P1/P2 removes only owned active rotation and reuses it on return', () => {
    let dto = createPatternPreset('digital-weave', 'switch', catalog), rotationId = dualOwner(dto)!.rotation.id
    for (const id of ['spectrum-fade','diagonal-tide','local-breath','coral-grains','ripple-center'] as const) {
      dto = patternPresetCandidate(openPatternPreset(dto, box, id, catalog), catalog)
      expect(dto.document.modifiers.find(m => m.id === rotationId)?.enabled).toBe(false)
      dto = patternPresetCandidate(openPatternPreset(dto, box, 'digital-weave', catalog), catalog)
      expect(dualOwner(dto)!.rotation.id).toBe(rotationId)
      expect(dto.document.modifiers.filter(m => m.type === 'rotation')).toHaveLength(1)
    }
  })
  it('imported mm anchor is converted once and unsafe legacy/position stacks are refused', () => {
    const dto = createExampleDocument('basic-grid','import'); dto.document.canvas.mm_per_unit = .5
    const draft = openPatternPreset(dto, box, 'digital-weave', catalog, false, { x: 21, y: 47 })
    expect(draft.fieldParameters).toMatchObject({ offset_x: 36.8, offset_y: 88.8, cell_width: 10.4 })
    expect(patternPresetCandidate(draft,catalog).document.elements).toEqual(dto.document.elements)
    dto.document.metadata['xiaomang_pattern_lab.shared_modifiers'] = { enabled: true, rotation_field: { mode: 'face_center' } }
    expect(() => openPatternPreset(dto,box,'digital-weave',catalog)).toThrow(/隐式旋转/)
    dto.document.metadata['xiaomang_pattern_lab.shared_modifiers'] = { enabled: true, modifiers: [{ type: 'position', enabled: true }] }
    expect(() => openPatternPreset(dto,box,'digital-weave',catalog)).toThrow(/位置/)
  })
  it('vortex declares real ellipse grid, complete Spiral and bell Size / linear Rotation', () => {
    const dto = createPatternPreset('vortex-scales', 'preset-vortex-scales', catalog)
    expect(dto.document_revision).toBe(0)
    expect((dto.document.metadata['xiaomang_pattern_lab.parametric'] as any).grid).toMatchObject({ rows: 12, columns: 12,
      spacing_x: 4.6, spacing_y: 4.6, element_width: 3.4, element_height: 1.6, lock_aspect: false, prototype: { kind: 'ellipse' } })
    const pair = dualOwner(dto)!, own = linearSizeOwner(dto)!
    expect(own.field.parameters).toEqual({ center_x: 30, center_y: 30, turns: 3, phase: .15, direction: 1, falloff: 1, invert: false })
    expect(pair.size.mapping).toMatchObject({ min_output: .74, max_output: 1.04, remap_curve: 'bell' })
    expect(pair.rotation.mapping).toMatchObject({ min_output: 0, max_output: 180, remap_curve: 'linear' })
    expect(pair.rotation.field_id).toBe(pair.size.field_id)
    expect(dto.document.modifiers).toHaveLength(2)
    const controls = patternPresetControls(openPatternPreset(dto, box, 'vortex-scales', catalog), catalog)
    expect(controls.group.parameters.map(p => p.id)).toEqual(['field_turns', 'field_phase', 'min_output', 'max_output'])
    if (process.env.PATTERN_PRESET_EVIDENCE_DIR) {
      mkdirSync(process.env.PATTERN_PRESET_EVIDENCE_DIR, { recursive: true })
      writeFileSync(`${process.env.PATTERN_PRESET_EVIDENCE_DIR}/vortex-scales.json`, JSON.stringify(dto, null, 2))
    }
  })
  it('vortex preview and Cancel leave source untouched; repeat, Reset and reload retain the owned graph', () => {
    const dto = createPatternPreset('vortex-scales', 'repeat-vortex', catalog), before = JSON.stringify(dto)
    const opened = openPatternPreset(dto, box, 'vortex-scales', catalog)
    const draft = changePatternPresetParameter(changePatternPresetParameter(opened, catalog, 'field_turns', 1.6), catalog, 'field_phase', .45)
    const candidate = patternPresetCandidate(draft, catalog)
    expect(JSON.stringify(dto)).toBe(before)
    expect(candidate.document_revision).toBe(dto.document_revision)
    expect(candidate.document.elements).toEqual(dto.document.elements)
    expect(dualOwner(candidate)!.record).toEqual(dualOwner(dto)!.record)
    const restored = JSON.parse(JSON.stringify(candidate))
    expect(openPatternPreset(restored, box, 'vortex-scales', catalog).fieldParameters).toMatchObject({ turns: 1.6, phase: .45 })
    expect(patternPresetCandidate(openPatternPreset(restored, box, 'vortex-scales', catalog), catalog).document).toEqual(candidate.document)
    expect(patternPresetCandidate(openPatternPreset(restored, box, 'vortex-scales', catalog, true), catalog).document).toEqual(dto.document)
  })
  it('vortex uses actual world bounds centre once, converts .5 mm once and protects other shared users', () => {
    const dto = createExampleDocument('basic-grid', 'irregular-original')
    dto.document.canvas.mm_per_unit = .5
    dto.document.metadata.fabric_config = { shape_source: 'original', output_mode: 'cells_only', height_mm: 2 }
    const offset = { min_x: 15, min_y: 40, max_x: 55, max_y: 60, width: 40, height: 20, units: 'mm' as const }
    const draft = openPatternPreset(dto, offset, 'vortex-scales', catalog, false, { x: 17, y: 42 })
    expect(draft.fieldParameters).toMatchObject({ center_x: 70, center_y: 100 })
    let result = patternPresetCandidate(draft, catalog)
    expect(result.document.elements).toEqual(dto.document.elements)
    expect(result.document.canvas).toEqual(dto.document.canvas)
    const own = linearSizeOwner(result)!, field = structuredClone(own.field)
    result.document.modifiers.push({ id: 'external-size', type: 'size', field_id: field.id, enabled: true, mapping: { min_output: .9, max_output: 1.1 } })
    result.document.metadata.fabric_config = { ...dto.document.metadata.fabric_config as object, field_modifiers: { height: { field_id: field.id, enabled: true } } }
    const candidate = patternPresetCandidate(changePatternPresetParameter(openPatternPreset(result, offset, 'vortex-scales', catalog), catalog, 'field_phase', .7), catalog)
    expect(candidate.document.fields.find(f => f.id === field.id)).toEqual(field)
    expect(candidate.document.modifiers.at(-1)).toEqual(result.document.modifiers.at(-1))
    expect(candidate.document.metadata.fabric_config).toEqual(result.document.metadata.fabric_config)
    expect(dualOwner(candidate)!.size.field_id).toBe(dualOwner(candidate)!.rotation.field_id)
    expect(dualOwner(candidate)!.size.field_id).not.toBe(field.id)
    const reset = openPatternPreset(candidate, box, 'vortex-scales', catalog, true)
    expect(reset.fieldParameters).toMatchObject({ center_x: 70, center_y: 100, phase: .15 })
  })
  it('all other presets replace only owned Size/Rotation without stacking; precision is explicit new-project only', () => {
    let dto = createPatternPreset('vortex-scales', 'cross-vortex', catalog)
    const rotation = dualOwner(dto)!.rotation.id
    for (const preset of patternPresets.filter(p => p.supportsCurrent && p.id !== 'vortex-scales')) {
      dto = patternPresetCandidate(openPatternPreset(dto, box, preset.id, catalog), catalog)
      expect(dto.document.modifiers.filter(m => m.type === 'size' && m.enabled !== false)).toHaveLength(preset.id === 'ripple-center' ? 0 : 1)
      expect(dto.document.modifiers.find(m => m.id === rotation)?.enabled).toBe(preset.id === 'digital-weave')
      dto = patternPresetCandidate(openPatternPreset(dto, box, 'vortex-scales', catalog), catalog)
      expect(dualOwner(dto)!.rotation.id).toBe(rotation)
      expect(dto.document.modifiers.filter(m => m.type === 'rotation' && m.enabled !== false)).toHaveLength(1)
      expect(dto.document.modifiers.filter(m => m.type === 'size' && m.enabled !== false)).toHaveLength(1)
    }
    expect(() => openPatternPreset(dto, box, 'precision-stagger', catalog)).toThrow(/不会重排/)
    const separate = createPatternPreset('precision-stagger', 'precision-separate', catalog)
    expect(separate.document.modifiers.some(m => m.type === 'rotation' && m.enabled !== false)).toBe(false)
    expect(dualOwner(dto)!.rotation.enabled).toBe(true)
  })
})
