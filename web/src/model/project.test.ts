import { describe, expect, it } from 'vitest'
import { directSourceElement, moveSourceElement, prepareProject, withMillimetreMapping } from './project'

function project(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    schema_version: 1,
    canvas: { width: 80, height: 50, unit: 'mm', mm_per_unit: 1 },
    reference: { source_path: '', visible: false, metadata: {}, preprocessing: {} },
    elements: [{ id: 'dot-1', type: 'circle', x: 10, y: 15, width: 4, height: 4, rotation: 0, visible: true, style: { fill: '#000' } }],
    groups: [], transforms: { 'dot-1': { element_id: 'dot-1', x: 10, y: 15, rotation: 0, scale_x: 1, scale_y: 1 } },
    metadata: {}, fields: [], modifiers: [],
    ...overrides,
  })
}

describe('official project → WM2 transport boundary', () => {
  it('wraps the existing PatternDocument schema without inventing another format', () => {
    const { dto, needsMillimetreMapping } = prepareProject(project(), 'test-id')
    expect(needsMillimetreMapping).toBe(false)
    expect(dto.document_id).toBe('test-id')
    expect(dto.document.elements[0].id).toBe('dot-1')
    expect(dto.assets).toEqual([])
  })

  it('rejects invalid JSON, duplicate elements and unknown types', () => {
    expect(() => prepareProject('{', 'a')).toThrow(/JSON/)
    expect(() => prepareProject(project({ elements: [{ id: 'x', type: 'future_type', x: 0, y: 0, width: 1, height: 1 }] }), 'a')).toThrow(/Element/)
    expect(() => prepareProject(project({ elements: [
      { id: 'x', type: 'circle', x: 0, y: 0, width: 1, height: 1 },
      { id: 'x', type: 'circle', x: 0, y: 0, width: 1, height: 1 },
    ] }), 'a')).toThrow(/Element/)
  })

  it('never sends old absolute asset paths to WM3', () => {
    const input = project({
      reference: { source_path: 'C:\\private\\image.png', metadata: { preprocessed_path: 'C:\\private\\binary.png' }, preprocessing: {} },
      metadata: { source_svg: 'C:\\private\\vector.svg' },
    })
    const { dto, warnings } = prepareProject(input, 'redacted')
    expect(JSON.stringify(dto)).not.toContain('C:')
    expect(warnings).toHaveLength(1)
  })

  it('requires an explicit mm mapping for old SVG-unit projects', () => {
    const old = prepareProject(project({ canvas: { width: 80, height: 50, unit: 'svg_user_unit', mm_per_unit: null } }), 'old')
    expect(old.needsMillimetreMapping).toBe(true)
    expect(() => withMillimetreMapping(old.dto, 0)).toThrow()
    expect(withMillimetreMapping(old.dto, 0.2).document.canvas.mm_per_unit).toBe(0.2)
  })

  it('maps only a matching free source ID and moves it once in document units', () => {
    const { dto } = prepareProject(project(), 'move')
    expect(directSourceElement(dto, 'dot-1', 10, 15)?.id).toBe('dot-1')
    expect(directSourceElement(dto, 'dot-1', 12, 15)).toBeNull()
    const next = moveSourceElement(dto, 'dot-1', 5, -2)
    expect(next.document_revision).toBe(1)
    expect(next.document.elements[0]).toMatchObject({ x: 15, y: 13 })
    expect(next.document.transforms['dot-1']).toMatchObject({ x: 15, y: 13 })
    expect(dto.document.elements[0]).toMatchObject({ x: 10, y: 15 })
    const generated = { ...dto, document: { ...dto.document, metadata: { 'xiaomang_pattern_lab.parametric': { mode: 'grid' } } } }
    expect(directSourceElement(generated, 'dot-1', 10, 15)).toBeNull()
  })
})
