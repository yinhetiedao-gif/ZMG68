import { describe, expect, it } from 'vitest'
import type { PatternDocumentDTO } from '../model/types'
import {
  addField, bindScalarModifierField, removeField, restoreSnapshot, setFieldEnabled,
  updateElement, updateField, updateGrid, updateLayout, updateReplacement,
  updateScalarModifier, updateStackModifier,
} from './editor'
import type { ParameterCatalog } from './parameterSchema'

function fixture(): PatternDocumentDTO {
  return {
    schema_version: '1.0', document_id: 'wm6', document_revision: 0, assets: [],
    document: {
      schema_version: 1,
      canvas: { width: 100, height: 80, unit: 'mm', mm_per_unit: 1 },
      reference: { source_path: '', visible: false }, groups: [],
      elements: [{ id: 'dot-1', type: 'circle', x: 10, y: 20, width: 4, height: 4, rotation: 0, visible: true }],
      transforms: { 'dot-1': { element_id: 'dot-1', x: 10, y: 20, rotation: 0, scale_x: 1, scale_y: 1 } },
      fields: [
        { id: 'wave-1', type: 'wave', parameters: { angle: 0, wavelength: 40, phase: 0, amplitude: 1, offset: 0, invert: false } },
        { id: 'mix-1', type: 'composite', parameters: { input_a_field_id: 'wave-1', input_b_field_id: 'wave-1', operator: 'multiply', mix: .5 } },
      ],
      modifiers: [
        { id: 'size-1', type: 'size', field_id: 'wave-1', enabled: true, mapping: { min_output: .6, max_output: 1.4, strength: 1, falloff: 1 } },
        { id: 'rotate-1', type: 'rotation', field_id: 'wave-1', enabled: true, mapping: { min_output: -30, max_output: 30, strength: 1, falloff: 1 } },
      ],
      metadata: {
        'xiaomang_pattern_lab.parametric': { mode: 'grid', family: 'grid', grid: { rows: 1, columns: 3, spacing_x: 20, spacing_y: 20, element_width: 4, element_height: 4, rotation: 0, offset_x: 20, offset_y: 20, lock_aspect: true }, model: { rows: 1, columns: 3, spacing_x: 20, spacing_y: 20, element_width: 4, element_height: 4, rotation: 0, offset_x: 20, offset_y: 20, lock_aspect: true } },
        'xiaomang_pattern_lab.shared_modifiers': { enabled: true, modifiers: [
          { id: 'position-1', type: 'position', enabled: true, parameters: { mode: 'offset', offset_x: 0, offset_y: 0, radius: 100, wavelength: 50, falloff: 1 } },
          { id: 'rotation-2', type: 'rotation', enabled: true, parameters: {} },
        ] },
        'xiaomang_pattern_lab.placement_assignment': { enabled: true, shape_prototypes: { circle: {}, star: {} }, replacement_map: {} },
      },
    },
  }
}

describe('WM6 centralized immutable document edits', () => {
  it('adds and removes schema-defined fields without changing layout, modifiers or source', () => {
    const initial = fixture()
    const catalog: ParameterCatalog = { schema_version: '1.0', units: 'mm', definitions: {
      layout: {}, modifier: {}, field: { noise: { label: '噪声', parameters: [
        { id: 'scale', label: '尺度', type: 'number', default: 50, value: 50, min: .01, max: 100,
          step: .1, unit: 'mm', options: [] },
      ] } },
    } }
    const added = addField(initial, 'noise', catalog)
    expect(added.id).toBe('field-1')
    expect(added.dto.document.fields.at(-1)).toMatchObject({ id: 'field-1', type: 'noise', parameters: { scale: 50 } })
    expect(added.dto.document.elements).toBe(initial.document.elements)
    expect(added.dto.document.metadata).toBe(initial.document.metadata)
    expect(added.dto.document.modifiers).toBe(initial.document.modifiers)
    const disabled = setFieldEnabled(added.dto, added.id, false)
    expect(disabled.document.fields.at(-1)?.enabled).toBe(false)
    const rebound = bindScalarModifierField(disabled, 'size-1', added.id)
    expect(rebound.document.modifiers[0].field_id).toBe(added.id)
    expect(() => removeField(rebound, added.id)).toThrow(/引用/)
    const restored = bindScalarModifierField(rebound, 'size-1', 'wave-1')
    const removed = removeField(restored, added.id)
    expect(removed.document.fields).toHaveLength(2)
    expect(removed.document.modifiers).toBe(restored.document.modifiers)
    expect(() => removeField(initial, 'wave-1')).toThrow(/引用/)
    expect(() => addField(initial, 'unknown', catalog)).toThrow()
  })
  it('edits Python-defined radial layout once without changing its source elements', () => {
    const initial = fixture()
    initial.document.metadata['xiaomang_pattern_lab.parametric'] = {
      mode: 'radial', model: { count: 12, center_x: 0 }, parametric_model: { count: 12, center_x: 0 },
    }
    const catalog: ParameterCatalog = { schema_version: '1.0', units: 'mm', definitions: {
      layout: { radial: { label: '放射', parameters: [
        { id: 'count', label: '数量', type: 'integer', default: 12, value: 12, min: 1, max: 3000,
          step: 1, unit: '', options: [] },
      ] } }, field: {}, modifier: {},
    } }
    const changed = updateLayout(initial, 'count', 20, catalog)
    expect(changed.document_revision).toBe(1)
    expect(changed.document.elements).toBe(initial.document.elements)
    expect(changed.document.metadata['xiaomang_pattern_lab.parametric']).toMatchObject({
      model: { count: 20 }, parametric_model: { count: 20 },
    })
    expect(() => updateLayout(initial, 'count', 2.5, catalog)).toThrow()
    expect(() => updateLayout(initial, 'unknown', 2, catalog)).toThrow()
  })
  it('commits source transform once without mutating the input', () => {
    const initial = fixture()
    const changed = updateElement(initial, 'dot-1', 'x', 25)
    expect(changed.document_revision).toBe(1)
    expect(changed.document.elements[0].x).toBe(25)
    expect(changed.document.transforms['dot-1'].x).toBe(25)
    expect(initial.document.elements[0].x).toBe(10)
  })

  it('updates only the named field and preserves composite references', () => {
    const initial = fixture()
    const changed = updateField(initial, 'wave-1', 'wavelength', 65)
    expect((changed.document.fields[0].parameters as Record<string, unknown>).wavelength).toBe(65)
    expect(changed.document.fields[1]).toBe(initial.document.fields[1])
    expect(() => updateField(initial, 'wave-1', 'wavelength', 0)).toThrow()
    expect(() => updateField(initial, 'mix-1', 'mix', .8)).toThrow(/只读/)
  })

  it('preserves modifier order and enables exact graph/stack edits', () => {
    const initial = fixture()
    const mapped = updateScalarModifier(initial, 'size-1', 'max_output', 1.8)
    expect(mapped.document.modifiers.map((item) => item.id)).toEqual(['size-1', 'rotate-1'])
    expect((mapped.document.modifiers[0].mapping as Record<string, unknown>).max_output).toBe(1.8)
    const disabled = updateScalarModifier(mapped, 'rotate-1', 'enabled', false)
    expect(disabled.document.modifiers[1].enabled).toBe(false)
    const positioned = updateStackModifier(disabled, 'position-1', 'offset_x', 8)
    const stack = positioned.document.metadata['xiaomang_pattern_lab.shared_modifiers'] as { modifiers: Array<{ id: string; parameters: { offset_x?: number } }> }
    expect(stack.modifiers.map((item) => item.id)).toEqual(['position-1', 'rotation-2'])
    expect(stack.modifiers[0].parameters.offset_x).toBe(8)
    expect(initial.document.modifiers[0].enabled).toBe(true)
  })

  it('keeps both persisted grid aliases synchronized and protects custom basis length', () => {
    const initial = fixture()
    const a = updateGrid(initial, 'columns', 4)
    const state = a.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { columns: number }; model: { columns: number } }
    expect(state.grid.columns).toBe(4)
    expect(state.model.columns).toBe(4)
    const basis = fixture()
    const parametric = basis.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: Record<string, unknown>; model: Record<string, unknown> }
    parametric.grid.basis_u_vector = [12, 16]
    parametric.model.basis_u_vector = [12, 16]
    const stretched = updateGrid(basis, 'spacing_x', 30)
    const stretchState = stretched.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { basis_u_vector: number[] } }
    expect(Math.hypot(...stretchState.grid.basis_u_vector)).toBeCloseTo(30)
  })

  it('updates an existing shape assignment without changing source geometry', () => {
    const initial = fixture()
    const shaped = updateReplacement(initial, 'dot-1', 'star')
    const state = shaped.document.metadata['xiaomang_pattern_lab.placement_assignment'] as { replacement_map: Record<string, string> }
    expect(state.replacement_map['dot-1']).toBe('star')
    expect(shaped.document.elements).toBe(initial.document.elements)
    expect(updateReplacement(shaped, 'dot-1', '').document.metadata['xiaomang_pattern_lab.placement_assignment']).toMatchObject({ replacement_map: {} })
  })

  it('restores snapshot content while revision stays monotonic', () => {
    const initial = fixture()
    const changed = updateField(initial, 'wave-1', 'amplitude', .6)
    const undone = restoreSnapshot(initial, changed.document_revision)
    expect(undone.document.fields).toEqual(initial.document.fields)
    expect(undone.document_revision).toBe(2)
    const redone = restoreSnapshot(changed, undone.document_revision)
    expect(redone.document_revision).toBe(3)
  })
})
