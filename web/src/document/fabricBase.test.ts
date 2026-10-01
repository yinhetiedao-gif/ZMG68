import { describe, expect, it } from 'vitest'
import type { PatternDocumentDTO } from '../model/types'
import type { ParameterCatalog, ParameterDefinition } from './parameterSchema'
import { fabricBase, setFabricBaseType, updateFabricBase } from './fabricBase'

const number = (id: string, value: number, min: number): ParameterDefinition => ({
  id, label: id, type: 'number', default: value, value, min, max: 10000, step: .1, unit: 'mm', options: [],
})
const catalog = { schema_version: '1.0', units: 'mm', definitions: { layout: {}, field: {}, modifier: {},
  fabric_base: { solid: { label: 'Solid', parameters: [number('thickness_mm', .6, .01), number('margin_mm', 0, 0)] },
    grid: { label: 'Grid', parameters: [number('thickness_mm', .6, .01), number('margin_mm', 0, 0),
      number('spacing_x_mm', 5, .01), number('spacing_y_mm', 5, .01), number('line_width_mm', 1, .01)] } },
} } as ParameterCatalog
const source = { schema_version: '1.0', document_id: 'doc', document_revision: 0, assets: [], document: {
  schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm' }, reference: {}, elements: [],
  groups: [], transforms: {}, metadata: { keep: 'original' }, fields: [], modifiers: [],
} } as PatternDocumentDTO

describe('F1 FabricConfig document edits', () => {
  it('is opt-in, versioned, undoable by snapshots, and never changes source elements', () => {
    expect(fabricBase(source)).toBeNull()
    const solid = setFabricBaseType(source, 'solid', catalog)
    expect(solid.document_revision).toBe(1)
    expect(fabricBase(solid)).toMatchObject({ type: 'solid', thickness_mm: .6, margin_mm: 0 })
    expect(solid.document.metadata.fabric_config).toMatchObject({ config_version: 1 })
    expect(source.document.metadata.fabric_config).toBeUndefined()
    const grid = setFabricBaseType(solid, 'grid', catalog)
    const edited = updateFabricBase(grid, 'line_width_mm', 2, catalog)
    expect(fabricBase(edited)).toMatchObject({ type: 'grid', spacing_x_mm: 5, line_width_mm: 2 })
    expect(edited.document.elements).toBe(source.document.elements)
    expect(edited.document.metadata.keep).toBe('original')
    expect(setFabricBaseType(edited, 'none', catalog).document.metadata.fabric_config).toBeUndefined()
  })

  it('rejects invalid values without committing', () => {
    const grid = setFabricBaseType(source, 'grid', catalog)
    expect(() => updateFabricBase(grid, 'spacing_x_mm', 0, catalog)).toThrow()
    expect(() => updateFabricBase(grid, 'line_width_mm', 6, catalog)).toThrow()
    expect(() => updateFabricBase(grid, 'thickness_mm', Number.NaN, catalog)).toThrow()
    expect(grid.document_revision).toBe(1)
  })
})
