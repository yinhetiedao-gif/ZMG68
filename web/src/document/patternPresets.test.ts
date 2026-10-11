import { describe, expect, it } from 'vitest'
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import base from '../test/sizeFieldCatalog.json'
import design from '../test/designCatalog.json'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { restoreSnapshot } from './editor'
import { linearSizeOwner } from './linearSize'
import { createPatternPreset, openPatternPreset, patternPresetCandidate, patternPresetControls,
  changePatternPresetParameter, patternPresetId, patternPresets, selectPatternPresetDriver } from './patternPresets'
import type { ParameterCatalog } from './parameterSchema'
const catalog = { ...base, definitions: { ...base.definitions, design } } as ParameterCatalog

describe('first three editable pattern recipes use the existing document graph', () => {
  it.each(patternPresets.filter(p => ['precision-stagger', 'spectrum-fade', 'diagonal-tide'].includes(p.id)))('$title creates a formal millimetre Grid document with explicit scope', preset => {
    const dto = createPatternPreset(preset.id, `preset-${preset.id}`, catalog)
    expect(dto.document.canvas).toMatchObject({ width: 60, height: 60, mm_per_unit: 1 })
    expect(dto.document_revision).toBe(0)
    expect(patternPresetId(dto)).toBe(preset.id)
    expect(dto.document.metadata['xiaomang_pattern_lab.example_id']).toBeUndefined()
    expect(dto.document.modifiers).toHaveLength(preset.field ? 1 : 0)
    expect(dto.document.fields).toHaveLength(preset.field ? 1 : 0)
    expect(dto).toEqual(JSON.parse(readFileSync(`../tests/fixtures/pattern_presets/${preset.id}.pattern.json`, 'utf8')))
    const draft = openPatternPreset(dto, phase1aBounds, preset.id, catalog)
    expect(patternPresetControls(draft, catalog).group.parameters).toHaveLength(3)
    if (process.env.PATTERN_PRESET_EVIDENCE_DIR) {
      mkdirSync(process.env.PATTERN_PRESET_EVIDENCE_DIR, { recursive: true })
      writeFileSync(`${process.env.PATTERN_PRESET_EVIDENCE_DIR}/${preset.id}.json`, JSON.stringify(dto, null, 2))
    }
  })
  it('effect candidate preserves holes/source/layout/Fabric/other effects; Cancel has nothing to undo', () => {
    const dto = createExampleDocument('gradient-grid', 'protected'), before = JSON.stringify(dto)
    dto.document.metadata.fabric_config = { shape_source: 'original', output_mode: 'cells_only', marker: 'keep' }
    const source = JSON.stringify(dto), draft = openPatternPreset(dto, phase1aBounds, 'diagonal-tide', catalog)
    const candidate = patternPresetCandidate(draft, catalog)
    expect(JSON.stringify(dto)).toBe(source)
    expect(candidate.document_revision).toBe(dto.document_revision)
    expect(candidate.document.elements).toBe(dto.document.elements)
    expect(candidate.document.transforms).toBe(dto.document.transforms)
    expect(candidate.document.metadata['xiaomang_pattern_lab.parametric']).toBe(dto.document.metadata['xiaomang_pattern_lab.parametric'])
    expect(candidate.document.metadata.fabric_config).toBe(dto.document.metadata.fabric_config)
    expect(candidate.document.modifiers.slice(0, dto.document.modifiers.length)).toEqual(dto.document.modifiers)
    expect(candidate.document.fields.slice(0, dto.document.fields.length)).toEqual(dto.document.fields)
    expect(before).not.toBe(source) // setup only; candidate never touches the source.
  })
  it('switching Linear/Wave edits one managed Size and never borrows user fields', () => {
    const source = createExampleDocument('gradient-grid', 'switch'), userFields = source.document.fields
    let current = source
    for (const id of ['spectrum-fade', 'diagonal-tide', 'spectrum-fade', 'diagonal-tide'] as const) {
      current = patternPresetCandidate(openPatternPreset(current, phase1aBounds, id, catalog), catalog)
      expect(current.document.modifiers).toHaveLength(source.document.modifiers.length + 1)
      expect(current.document.fields.slice(0, userFields.length)).toEqual(userFields)
    }
    expect(current.document.fields).toHaveLength(userFields.length + 2)
    expect(linearSizeOwner(current)?.field.type).toBe('wave')
  })
  it('shared recipe fields are copy-isolated without changing Fabric bindings', () => {
    const source = createPatternPreset('spectrum-fade', 'shared', catalog), owned = linearSizeOwner(source)!
    source.document.metadata.fabric_config = { field_modifiers: { height: { enabled: true, field_id: owned.field.id } } }
    const draft = changePatternPresetParameter(openPatternPreset(source, phase1aBounds, 'spectrum-fade', catalog), catalog, 'angle', 45)
    const result = patternPresetCandidate(draft, catalog)
    expect(linearSizeOwner(result)?.field.id).not.toBe(owned.field.id)
    expect(result.document.fields.find(f => f.id === owned.field.id)).toEqual(owned.field)
    expect(result.document.metadata.fabric_config).toEqual(source.document.metadata.fabric_config)
    expect(result.document.modifiers).toHaveLength(1)
  })
  it('Reset/serialization/history retain the recipe graph but do not reset public controls', () => {
    const source = createPatternPreset('diagonal-tide', 'restore', catalog)
    source.document.metadata.web_design_controls = { ...(source.document.metadata.web_design_controls as object), size_percent: 90, seed: 77 }
    let draft = openPatternPreset(source, phase1aBounds, 'diagonal-tide', catalog)
    draft = changePatternPresetParameter(draft, catalog, 'field_wavelength', 31)
    const applied = { ...patternPresetCandidate(draft, catalog), document_revision: source.document_revision + 1 }
    const restored = JSON.parse(JSON.stringify(applied)), reopened = openPatternPreset(restored, phase1aBounds, 'diagonal-tide', catalog)
    expect(reopened.fieldParameters?.wavelength).toBe(31)
    const reset = patternPresetCandidate(openPatternPreset(restored, phase1aBounds, 'diagonal-tide', catalog, true), catalog)
    expect(linearSizeOwner(reset)?.field.parameters).toHaveProperty('wavelength', 23)
    expect(reset.document.metadata.web_design_controls).toEqual(source.document.metadata.web_design_controls)
    expect(restoreSnapshot(source, 1).document).toEqual(source.document)
    expect(restoreSnapshot(applied, 2).document).toEqual(applied.document)
  })
  it('precision cannot reorder an imported/current unrelated project', () => {
    expect(() => openPatternPreset(createExampleDocument('basic-grid', 'existing'), phase1aBounds, 'precision-stagger', catalog)).toThrow('不会重排')
    const source = createPatternPreset('precision-stagger', 'precision', catalog), original = JSON.stringify(source)
    const next = patternPresetCandidate(changePatternPresetParameter(openPatternPreset(source, phase1aBounds, 'precision-stagger', catalog), catalog, 'preset_spacing_y', 6.5), catalog)
    expect(JSON.stringify(source)).toBe(original)
    expect(next.document.fields).toHaveLength(0)
    expect(next.document.modifiers).toHaveLength(0)
  })
  it('an explicit advanced driver change becomes custom on Apply, never a falsely labeled recipe', () => {
    const source = createPatternPreset('diagonal-tide', 'custom', catalog)
    const draft = selectPatternPresetDriver(openPatternPreset(source, phase1aBounds, 'diagonal-tide', catalog), 'stripe', catalog)
    expect(draft.presetId).toBe('')
    const result = patternPresetCandidate(draft, catalog)
    expect(patternPresetId(result)).toBeNull()
    expect(patternPresetId(source)).toBe('diagonal-tide')
    expect(result.document.modifiers).toHaveLength(1)
    expect(result.document.fields.find(f => f.type === 'wave')).toEqual(source.document.fields[0])
  })
  it('world/mm conversion is applied once and board/XY/rotations are preserved', () => {
    const dto = createExampleDocument('basic-grid', 'units'); dto.document.canvas = { ...dto.document.canvas, mm_per_unit: .5, origin_x: 20, origin_y: 40, width: 120, height: 80 }
    const wave = patternPresetCandidate(openPatternPreset(dto, phase1aBounds, 'diagonal-tide', catalog), catalog)
    expect(linearSizeOwner(wave)?.field.parameters).toHaveProperty('wavelength', 46)
    expect(wave.document.canvas).toBe(dto.document.canvas)
    expect(wave.document.transforms).toBe(dto.document.transforms)
    expect(wave.document.elements).toBe(dto.document.elements)
    expect(patternPresetControls(openPatternPreset(wave, phase1aBounds, 'diagonal-tide', catalog), catalog).values.field_wavelength).toBe(23)
  })
})
