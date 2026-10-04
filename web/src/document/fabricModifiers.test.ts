import { describe, expect, it } from 'vitest'
import type { PatternDocumentDTO } from '../model/types'
import type { ParameterCatalog, ParameterDefinition } from './parameterSchema'
import { availableFabricFields, fabricFieldModifier, setFabricModifierEnabled,
  setFabricModifierField, updateFabricModifier } from './fabricModifiers'
import { removeField } from './editor'

const number = (id: string, initial: number): ParameterDefinition => ({ id, label: id,
  type: 'number', default: initial, value: initial, min: 0, max: 100, step: .1, unit: '', options: [] })
const catalog = { schema_version: '1.0', units: 'mm', definitions: { layout: {}, field: {}, modifier: {},
  fabric_modifier: {
    height: { label: 'Height', parameters: [number('min_height_mm', 1), number('max_height_mm', 5)] },
    scale: { label: 'Scale', parameters: [number('min_scale', .5), number('max_scale', 1.5)] },
    density: { label: 'Density', parameters: [number('threshold', .5)] },
    orientation: { label: 'Orientation', parameters: [number('min_angle_deg', -45), number('max_angle_deg', 45)] },
  } } } as ParameterCatalog
const dto = { schema_version: '1.0', document_id: 'f3', document_revision: 4, assets: [],
  document: { schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm' },
    reference: {}, elements: [], groups: [], transforms: {}, modifiers: [],
    fields: [{ id: 'wave', type: 'wave' }, { id: 'linear', type: 'linear' },
      { id: 'image', type: 'image' }],
    metadata: { fabric_config: { config_version: 1, base: { type: 'solid', thickness_mm: .6 },
      unit_cell: { type: 'fin', width_mm: 2, depth_mm: 2, height_mm: 3 } } },
  } } as PatternDocumentDTO

describe('F3 Fabric field binding', () => {
  it('allows image consumers but keeps image-derived Orientation out of F4-A', () => {
    const composed = structuredClone(dto)
    composed.document.fields.push({ id: 'image-composite', type: 'composite', parameters: {
      input_a_field_id: 'image', input_b_field_id: 'wave', operator: 'multiply' } })
    expect(availableFabricFields(composed, 'height').map(f => f.id)).toContain('image-composite')
    expect(availableFabricFields(composed, 'orientation').map(f => f.id)).toEqual(['wave', 'linear'])
    const orientation = setFabricModifierEnabled(composed, 'orientation', true, catalog)
    expect(() => setFabricModifierField(orientation, 'orientation', 'image')).toThrow()
    const height = setFabricModifierField(setFabricModifierEnabled(dto, 'height', true, catalog), 'height', 'image')
    const scale = setFabricModifierField(setFabricModifierEnabled(height, 'scale', true, catalog), 'scale', 'image')
    expect(fabricFieldModifier(scale, 'height')?.field_id).toBe('image')
    expect(fabricFieldModifier(scale, 'scale')?.field_id).toBe('image')
  })
  it('allows one shared field to drive multiple modifiers without mutating input', () => {
    const height = setFabricModifierEnabled(dto, 'height', true, catalog)
    const scale = setFabricModifierEnabled(height, 'scale', true, catalog)
    expect(scale.document_revision).toBe(dto.document_revision + 2)
    expect(fabricFieldModifier(scale, 'height')).toMatchObject({ field_id: 'wave', min_height_mm: 1 })
    expect(fabricFieldModifier(scale, 'scale')).toMatchObject({ field_id: 'wave', max_scale: 1.5 })
    expect(dto.document.metadata.fabric_config).not.toHaveProperty('field_modifiers')
    expect(availableFabricFields(dto).map((field) => field.id)).toEqual(['wave', 'linear', 'image'])
    expect(() => removeField(scale, 'wave')).toThrow(/Fabric/)
  })

  it('updates field and parameters once, and rejects invalid values', () => {
    const enabled = setFabricModifierEnabled(dto, 'height', true, catalog)
    const rebound = setFabricModifierField(enabled, 'height', 'linear')
    const updated = updateFabricModifier(rebound, 'height', 'max_height_mm', 6, catalog)
    expect(updated.document_revision).toBe(dto.document_revision + 3)
    expect(fabricFieldModifier(updated, 'height')).toMatchObject({ field_id: 'linear', max_height_mm: 6 })
    expect(setFabricModifierField(updated, 'height', 'linear')).toBe(updated)
    expect(() => setFabricModifierField(updated, 'height', 'missing')).toThrow()
    expect(() => updateFabricModifier(updated, 'height', 'max_height_mm', Number.NaN, catalog)).toThrow()
    expect(() => updateFabricModifier(updated, 'height', 'max_height_mm', 0, catalog)).toThrow()
    expect(updated.document_revision).toBe(dto.document_revision + 3)
  })

  it('disables only the selected modifier in one revision', () => {
    const height = setFabricModifierEnabled(dto, 'height', true, catalog)
    const scale = setFabricModifierEnabled(height, 'scale', true, catalog)
    const disabled = setFabricModifierEnabled(scale, 'height', false, catalog)
    expect(disabled.document_revision).toBe(scale.document_revision + 1)
    expect(fabricFieldModifier(disabled, 'height')?.enabled).toBe(false)
    expect(fabricFieldModifier(disabled, 'scale')?.enabled).toBe(true)
    expect(setFabricModifierEnabled(disabled, 'height', false, catalog)).toBe(disabled)
  })
})
