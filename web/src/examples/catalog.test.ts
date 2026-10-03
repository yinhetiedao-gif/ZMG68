import { describe, expect, it } from 'vitest'
import { createExampleDocument, exampleIdFromDocument, examples } from './catalog'
import { restoreSnapshot, updateField, updateGrid, updateScalarModifier } from '../document/editor'

describe('versioned built-in PatternDocument fixtures', () => {
  it('opens a normal 3×3 Grid document and edits its existing layout model', () => {
    const dto = createExampleDocument('basic-grid', 'example-1')
    expect(dto.schema_version).toBe('1.0')
    expect(dto.document.schema_version).toBe(1)
    expect(dto.document.elements).toHaveLength(9)
    expect(exampleIdFromDocument(dto)).toBe('basic-grid')
    const rows = updateGrid(dto, 'rows', 4)
    const columns = updateGrid(rows, 'columns', 5)
    const spacing = updateGrid(columns, 'spacing_x', 18)
    const size = updateGrid(spacing, 'element_width', 10)
    const grid = size.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: Record<string, number> }
    expect(grid.grid).toMatchObject({ rows: 4, columns: 5, spacing_x: 18, element_width: 10, element_height: 10 })
    expect(dto.document.elements).toHaveLength(9)
  })

  it('opens a gradient with one shared Field and existing Size/Rotation modifiers', () => {
    const dto = createExampleDocument('gradient-grid', 'example-2')
    expect(dto.document.elements).toHaveLength(16)
    expect(dto.document.fields).toMatchObject([{ id: 'linear-1', type: 'linear' }])
    expect(dto.document.modifiers.map((item) => [item.type, item.field_id]))
      .toEqual([['size', 'linear-1'], ['rotation', 'linear-1']])
    const fieldEdited = updateField(dto, 'linear-1', 'angle', 30)
    const sizeEdited = updateScalarModifier(fieldEdited, 'size-1', 'max_output', 2)
    expect(sizeEdited.document.fields[0].parameters).toMatchObject({ angle: 30 })
    expect(sizeEdited.document.modifiers[0].mapping).toMatchObject({ max_output: 2 })
    expect(dto.document.fields[0].parameters).toMatchObject({ angle: 0 })
  })

  it('restores an original fixture as one undoable document revision', () => {
    const original = createExampleDocument('basic-grid', 'same-project')
    const edited = updateGrid(original, 'rows', 5)
    const reset = restoreSnapshot(createExampleDocument('basic-grid', edited.document_id), edited.document_revision)
    expect(reset.document_revision).toBe(edited.document_revision + 1)
    expect((reset.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(3)
    expect(edited.document_id).toBe(reset.document_id)
  })

  it('advertises only existing editable and standard 2D STL capabilities', () => {
    expect(examples).toHaveLength(2)
    expect(examples.every((item) => item.capabilities.includes('editable') && item.capabilities.includes('standard_stl'))).toBe(true)
    expect(examples.every((item) => !item.capabilities.includes('preview_only'))).toBe(true)
  })
})
