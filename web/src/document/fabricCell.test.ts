import { describe, expect, it } from 'vitest'
import { fabricPlacement, fabricUnitCell, setFabricUnitCellType, updateFabricUnitCell } from './fabricCell'
import type { ParameterCatalog, ParameterDefinition } from './parameterSchema'
import type { PatternDocumentDTO } from '../model/types'

const parameter = (id: string, value: number): ParameterDefinition => ({ id, label: id, type: 'number',
  default: value, value, min: .01, max: 10000, step: .1, unit: 'mm', options: [] })
const catalog = { schema_version: '1.0', units: 'mm', definitions: { layout: {}, field: {}, modifier: {},
  fabric_cell: Object.fromEntries(['cylinder', 'cone', 'pyramid', 'double_tower', 'fin'].map((type) => [type,
    { label: type, parameters: [parameter('width_mm', 2), parameter('depth_mm', 2), parameter('height_mm', 3)] }])),
  fabric_placement: { regular: { label: 'regular', parameters: [parameter('spacing_x_mm', 5), parameter('spacing_y_mm', 5)] } },
} } as ParameterCatalog
const dto = { schema_version: '1.0', document_id: 'f2', document_revision: 0, assets: [],
  document: { schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm' },
    reference: {}, elements: [], groups: [], transforms: {}, fields: [], modifiers: [],
    metadata: { fabric_config: { config_version: 1, base: { type: 'solid', thickness_mm: .6, margin_mm: 0 } } },
  } } as PatternDocumentDTO

describe('F2 Unit Cell document editing', () => {
  it('uses one immutable revision per change, preserves base, and removes both plan inputs together', () => {
    const cylinder = setFabricUnitCellType(dto, 'cylinder', catalog)
    expect(cylinder.document_revision).toBe(1)
    expect(fabricUnitCell(cylinder)).toMatchObject({ type: 'cylinder', width_mm: 2, height_mm: 3 })
    expect(fabricPlacement(cylinder)).toEqual({ spacing_x_mm: 5, spacing_y_mm: 5 })
    const resized = updateFabricUnitCell(cylinder, 'cell', 'height_mm', 4, catalog)
    const spaced = updateFabricUnitCell(resized, 'placement', 'spacing_x_mm', 6, catalog)
    expect(spaced.document_revision).toBe(3)
    expect(fabricUnitCell(spaced)?.height_mm).toBe(4)
    expect(fabricPlacement(spaced)?.spacing_x_mm).toBe(6)
    expect(spaced.document.metadata.fabric_config).toMatchObject({ base: { thickness_mm: .6 } })
    expect(dto.document.metadata.fabric_config).not.toHaveProperty('unit_cell')
    const fin = setFabricUnitCellType(spaced, 'fin', catalog)
    expect(fabricUnitCell(fin)).toMatchObject({ type: 'fin', height_mm: 4 })
    expect(fabricPlacement(fin)?.spacing_x_mm).toBe(6)
    const removed = setFabricUnitCellType(fin, 'none', catalog)
    expect(fabricUnitCell(removed)).toBeNull()
    expect(fabricPlacement(removed)).toBeNull()
    expect(removed.document.metadata.fabric_config).toMatchObject({ base: { type: 'solid' } })
  })

  it('rejects invalid dimensions without changing the previous document', () => {
    const cylinder = setFabricUnitCellType(dto, 'cylinder', catalog)
    expect(() => updateFabricUnitCell(cylinder, 'cell', 'height_mm', 0, catalog)).toThrow()
    expect(() => updateFabricUnitCell(cylinder, 'placement', 'spacing_y_mm', Number.NaN, catalog)).toThrow()
    expect(cylinder.document_revision).toBe(1)
  })
})
