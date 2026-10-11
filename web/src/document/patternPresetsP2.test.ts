import { describe, expect, it } from 'vitest'
import { mkdirSync, writeFileSync } from 'node:fs'
import base from '../test/sizeFieldCatalog.json'
import design from '../test/designCatalog.json'
import { createExampleDocument } from '../examples/catalog'
import { linearSizeOwner } from './linearSize'
import { openRadialSize, radialSizeCandidate, radialSizeLayer } from './radialSize'
import { STACK_KEY } from './selectors'
import { designValues } from './designControls'
import { createPatternPreset, openPatternPreset, patternPresetCandidate, patternPresetControls, changePatternPresetParameter, patternPresetId } from './patternPresets'
import type { ParameterCatalog } from './parameterSchema'
const catalog = { ...base, definitions: { ...base.definitions, design } } as ParameterCatalog
const ids = ['local-breath', 'coral-grains', 'ripple-center'] as const
const box = { min_x: 20, min_y: 40, max_x: 80, max_y: 80, width: 60, height: 40, units: 'mm' as const }

describe('P2 recipes adapt the existing scalar and ordered radial candidate paths', () => {
  it.each(ids)('%s creates a portable editable graph without manufacturing or source mutation', id => {
    const dto = createPatternPreset(id, `preset-${id}`, catalog)
    expect(dto.document_revision).toBe(0)
    expect(patternPresetId(dto)).toBe(id)
    const source = JSON.stringify(dto), draft = openPatternPreset(dto, box, id, catalog)
    const next = patternPresetCandidate(draft, catalog)
    expect(JSON.stringify(dto)).toBe(source)
    expect(next.document_revision).toBe(0)
    expect(patternPresetControls(draft, catalog).group.parameters.length).toBeGreaterThanOrEqual(3)
    expect(openPatternPreset(JSON.parse(JSON.stringify(next)), box, id, catalog).values).toEqual(draft.values)
    if (process.env.PATTERN_PRESET_EVIDENCE_DIR) {
      mkdirSync(process.env.PATTERN_PRESET_EVIDENCE_DIR, { recursive: true })
      writeFileSync(`${process.env.PATTERN_PRESET_EVIDENCE_DIR}/${id}.json`, JSON.stringify(dto, null, 2))
    }
  })
  it('local defaults include a real ellipse and disabled curve, with one common multiplier', () => {
    const dto = createExampleDocument('basic-grid', 'breath'), before = JSON.stringify(dto)
    let draft = openPatternPreset(dto, box, 'local-breath', catalog)
    expect(draft.values).toMatchObject({ min_output: 1.3, max_output: 1.3, scope_mode: 'areas' })
    expect(draft.influenceAreas?.map(a => [a.type, a.enabled])).toEqual([['ellipse', true], ['curve', false]])
    expect(draft.influenceAreas?.[0].parameters).toMatchObject({ x: 45.2, y: 60 })
    draft = changePatternPresetParameter(draft, catalog, 'preset_ratio', .8)
    draft = changePatternPresetParameter(draft, catalog, 'preset_area_width', 18)
    draft = changePatternPresetParameter(draft, catalog, 'preset_area_feather', 3)
    const next = patternPresetCandidate(draft, catalog), owner = linearSizeOwner(next)!
    expect(owner.modifier.mapping).toMatchObject({ min_output: .8, max_output: .8 })
    expect((owner.modifier.influence_areas as any[])[0].parameters).toMatchObject({ width: 18, feather: 3 })
    expect(JSON.stringify(dto)).toBe(before)
    const edit = openPatternPreset(next, { ...box, min_x: 999, width: 50 }, 'local-breath', catalog)
    expect(edit.bounds).toEqual(box)
    const edited = patternPresetCandidate(changePatternPresetParameter(edit, catalog, 'preset_ratio', 1.4), catalog)
    expect(openPatternPreset(edited, { ...box, min_x: 999 }, 'local-breath', catalog, true).influenceAreas?.[0].parameters.x).toBe(45.2)
    const reset = openPatternPreset(next, { ...box, min_x: 999 }, 'local-breath', catalog, true)
    expect(reset.influenceAreas?.[0].parameters.x).toBe(45.2)
    expect(reset.values.max_output).toBe(1.3)
  })
  it('Noise applied to an existing artwork does not change public random, source, board, layout or Fabric', () => {
    const dto = createExampleDocument('gradient-grid', 'user')
    dto.document.metadata.fabric_config = { marker: 'unchanged', shape_source: 'original' }
    dto.document.metadata.web_design_controls = { version: 1, ...designValues(dto, catalog), seed: 88, position_jitter: .1, rotation: 19 }
    const original = JSON.stringify(dto), draft = openPatternPreset(dto, box, 'coral-grains', catalog)
    const next = patternPresetCandidate(draft, catalog)
    expect(next.document.metadata.web_design_controls).toEqual(dto.document.metadata.web_design_controls)
    expect(next.document.metadata.fabric_config).toBe(dto.document.metadata.fabric_config)
    expect(next.document.canvas).toBe(dto.document.canvas)
    expect(next.document.elements).toBe(dto.document.elements)
    expect(next.document.fields.slice(0, dto.document.fields.length)).toEqual(dto.document.fields)
    expect(JSON.stringify(dto)).toBe(original)
    expect(linearSizeOwner(next)?.field.parameters).toMatchObject({ scale: 14, seed: 27, contrast: 1.5, octaves: 3 })
    const plain = createExampleDocument('basic-grid', 'plain')
    delete plain.document.metadata.web_design_controls
    const applied = patternPresetCandidate(openPatternPreset(plain, box, 'coral-grains', catalog), catalog)
    expect(applied.document.metadata.web_design_controls).toBeUndefined()
    const reopened = patternPresetCandidate(openPatternPreset(applied, box, 'coral-grains', catalog), catalog)
    expect(reopened.document.metadata.web_design_controls).toBeUndefined()
  })
  it('coral tracks only explicitly edited random keys, restores them on switch, and preserves independent user edits', () => {
    const source = createExampleDocument('basic-grid', 'jitter'); source.document.canvas.mm_per_unit = .5
    let draft = openPatternPreset(source, box, 'coral-grains', catalog)
    draft = changePatternPresetParameter(draft, catalog, 'preset_jitter', .7)
    const next = patternPresetCandidate(draft, catalog)
    expect(designValues(next, catalog).position_jitter).toBe(.7)
    expect((next.document.metadata.web_pattern_preset as any).random_after.position_jitter).toBe(1.4)
    const switched = patternPresetCandidate(openPatternPreset(next, box, 'local-breath', catalog), catalog)
    expect(designValues(switched, catalog).position_jitter).toBe(0)
    next.document.metadata.web_design_controls = { ...(next.document.metadata.web_design_controls as object), position_jitter: 2, seed: 99 }
    const independent = patternPresetCandidate(openPatternPreset(next, box, 'ripple-center', catalog), catalog)
    expect(designValues(independent, catalog)).toMatchObject({ position_jitter: 1, seed: 99 })
  })
  it('shared Noise is copy-isolated and Reset does not replace user public parameters', () => {
    const dto = createPatternPreset('coral-grains', 'shared', catalog), old = linearSizeOwner(dto)!
    dto.document.metadata.fabric_config = { field_modifiers: { height: { enabled: true, field_id: old.field.id } } }
    dto.document.metadata.web_design_controls = { ...(dto.document.metadata.web_design_controls as object), rotation: 21, size_percent: 83 }
    const draft = changePatternPresetParameter(openPatternPreset(dto, box, 'coral-grains', catalog), catalog, 'field_scale', 20)
    const next = patternPresetCandidate(draft, catalog)
    expect(linearSizeOwner(next)?.field.id).not.toBe(old.field.id)
    expect(next.document.fields.find(f => f.id === old.field.id)).toEqual(old.field)
    expect(next.document.metadata.fabric_config).toEqual(dto.document.metadata.fabric_config)
    const reset = patternPresetCandidate(openPatternPreset(next, box, 'coral-grains', catalog, true), catalog)
    expect(designValues(reset, catalog)).toMatchObject({ rotation: 21, size_percent: 83 })
  })
  it('radial owns a separate layer, never repurposes a user radial shortcut, and freezes its initial world bounds', () => {
    const source = createExampleDocument('basic-grid', 'radial'); source.document.canvas.mm_per_unit = .5
    const user = radialSizeCandidate(openRadialSize(source, box), catalog), userLayer = radialSizeLayer(user)!
    const draft = openPatternPreset(user, box, 'ripple-center', catalog)
    expect(draft.values).toMatchObject({ center_x: 50, center_y: 60, min_scale: 1.25, max_scale: .65 })
    const next = patternPresetCandidate(draft, catalog)
    expect(radialSizeLayer(next)).toEqual(userLayer)
    const record = next.document.metadata.web_pattern_preset as any
    expect(record.radial_layer_id).not.toBe(userLayer.id)
    const layers = (next.document.metadata[STACK_KEY] as any).modifiers
    expect(layers.find((l: any) => l.id === record.radial_layer_id).parameters).toMatchObject({ center_x: 100, center_y: 120, radius: Math.hypot(60, 40) })
    const edit = openPatternPreset(JSON.parse(JSON.stringify(next)), { ...box, min_x: 999 }, 'ripple-center', catalog)
    expect(edit.values).toEqual(draft.values)
    const reset = openPatternPreset(next, { ...box, min_x: 999 }, 'ripple-center', catalog, true)
    expect(reset.values.center_x).toBe(50)
  })
  it('six-recipe switching reuses owned layer IDs and leaves all independent fields/effects unchanged', () => {
    let dto = createExampleDocument('gradient-grid', 'switch'), fields = structuredClone(dto.document.fields), modifiers = structuredClone(dto.document.modifiers)
    for (const id of ['spectrum-fade', 'local-breath', 'ripple-center', 'coral-grains', 'diagonal-tide', 'ripple-center', 'local-breath', 'ripple-center'] as const) {
      dto = patternPresetCandidate(openPatternPreset(dto, box, id, catalog), catalog)
      expect(dto.document.fields.slice(0, fields.length)).toEqual(fields)
      expect(dto.document.modifiers.slice(0, modifiers.length)).toEqual(modifiers)
      const stack = dto.document.metadata[STACK_KEY] as any
      const activeOwned = dto.document.modifiers.filter(m => !modifiers.some(user => user.id === m.id) && m.enabled !== false).length + (stack?.modifiers ?? []).filter((m: any) => m.enabled !== false).length
      expect(activeOwned).toBe(1)
    }
    expect((dto.document.metadata[STACK_KEY] as any).modifiers).toHaveLength(1)
    expect(dto.document.modifiers).toHaveLength(modifiers.length + 1)
  })
  it('an explicit millimetre mapping change scales the saved initialization frame exactly once on Reset', () => {
    const dto = createPatternPreset('ripple-center', 'resized', catalog)
    dto.document.canvas.mm_per_unit = .5
    const edit = openPatternPreset(dto, box, 'ripple-center', catalog)
    expect(edit.values.center_x).toBe(15)
    const reset = openPatternPreset(dto, box, 'ripple-center', catalog, true)
    expect(reset.values.center_x).toBe(15)
    expect(reset.values.radius).toBeCloseTo(Math.hypot(51.2,51.2)/4)
  })
})
