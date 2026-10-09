import { describe, expect, it } from 'vitest'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { openLinearSize, linearSizeCandidate, linearSizeOwner, linearSizeGroup, linearSizeDefaults } from './linearSize'
import { restoreSnapshot } from './editor'
import { linearCatalog } from '../test/linearSizeFixture'
describe('owned 2D linear size configuration', () => {
  it('builds a display-only candidate and preserves Grid/source/other configurations', () => {
    const dto = createExampleDocument('basic-grid', 'grid'), before = JSON.stringify(dto)
    const draft = openLinearSize(dto, phase1aBounds), next = linearSizeCandidate(draft, linearCatalog)
    expect(JSON.stringify(dto)).toBe(before)
    expect(next.document_revision).toBe(dto.document_revision)
    expect(next.document.elements).toBe(dto.document.elements)
    expect(next.document.metadata['xiaomang_pattern_lab.parametric']).toBe(dto.document.metadata['xiaomang_pattern_lab.parametric'])
    expect(next.document.fields).toHaveLength(1); expect(next.document.modifiers).toHaveLength(1)
    expect(next.document.modifiers[0].field_id).toBe(next.document.fields[0].id)
  })
  it('updates the same owner once; persistence and history retain full references', () => {
    const dto = createExampleDocument('basic-grid', 'grid')
    const applied = { ...linearSizeCandidate(openLinearSize(dto, phase1aBounds), linearCatalog), document_revision: 1 }
    const restored = JSON.parse(JSON.stringify(applied))
    const draft = openLinearSize(restored, phase1aBounds); draft.values.angle = 45
    const edited = linearSizeCandidate(draft, linearCatalog)
    expect(edited.document.fields).toHaveLength(1); expect(edited.document.modifiers).toHaveLength(1)
    expect(linearSizeOwner(edited)?.owner.field_id).toBe(linearSizeOwner(applied)?.owner.field_id)
    expect(openLinearSize(edited, phase1aBounds).values.angle).toBe(45)
    expect(restoreSnapshot(dto, 1).document.fields).toHaveLength(0)
    expect(restoreSnapshot(edited, 2).document.modifiers).toEqual(edited.document.modifiers)
  })
  it('does not borrow or modify user Linear fields, and copies a shortcut field shared by Fabric/Composite', () => {
    const dto = createExampleDocument('gradient-grid', 'grid'), original = JSON.stringify(dto.document.fields)
    const candidate = linearSizeCandidate(openLinearSize(dto, phase1aBounds), linearCatalog)
    expect(JSON.stringify(candidate.document.fields.slice(0, dto.document.fields.length))).toBe(original)
    const owner = linearSizeOwner(candidate)!
    candidate.document.metadata.fabric_config = { field_modifiers: { height: { field_id: owner.field.id, enabled: false } } }
    candidate.document.fields.push({ id: 'composite-user', type: 'composite', parameters: { input_a_field_id: owner.field.id } })
    const draft = openLinearSize(candidate, phase1aBounds); draft.values.angle = 90
    const next = linearSizeCandidate(draft, linearCatalog)
    expect(linearSizeOwner(next)?.field.id).not.toBe(owner.field.id)
    expect(next.document.fields.find(item => item.id === owner.field.id)).toEqual(owner.field)
    expect(next.document.metadata.fabric_config).toBe(candidate.document.metadata.fabric_config)
    expect(next.document.modifiers).toHaveLength(candidate.document.modifiers.length)
    const again = linearSizeCandidate(openLinearSize(next, phase1aBounds), linearCatalog)
    expect(again.document.fields).toHaveLength(next.document.fields.length)
  })
  it('converts actual nonzero mm bounds to native world units (not window coordinates)', () => {
    const dto = createExampleDocument('basic-grid', 'grid'); dto.document.canvas.mm_per_unit = .5
    const draft = openLinearSize(dto, phase1aBounds)
    const next = linearSizeCandidate(draft, linearCatalog)
    expect(linearSizeOwner(next)?.field.parameters).toEqual({ angle: 0, start: 20, end: 140 })
    const resized = structuredClone(next); resized.document.canvas.mm_per_unit = 1
    expect(openLinearSize(resized, phase1aBounds).bounds.min_x).toBe(20)
    expect(linearSizeOwner(linearSizeCandidate(openLinearSize(resized, phase1aBounds), linearCatalog))?.field.parameters).toEqual({ angle: 0, start: 20, end: 140 })
    draft.values.angle = 180
    expect((linearSizeOwner(linearSizeCandidate(draft, linearCatalog))?.field.parameters as Record<string, number>).start).toBeCloseTo(-140)
  })
  it('reuses the owned Size ID after advanced rebind/removal, without altering the borrowed user field', () => {
    const dto = linearSizeCandidate(openLinearSize(createExampleDocument('basic-grid', 'grid'), phase1aBounds), linearCatalog)
    const owner = linearSizeOwner(dto)!
    const userField = { id: 'user-linear', type: 'linear', enabled: true, parameters: { angle: 72, start: 0, end: 100 } }
    dto.document.fields = [userField]
    dto.document.modifiers = dto.document.modifiers.map(item => ({ ...item, field_id: userField.id }))
    const next = linearSizeCandidate(openLinearSize(dto, phase1aBounds), linearCatalog)
    expect(next.document.modifiers).toHaveLength(1)
    expect(next.document.modifiers[0].id).toBe(owner.modifier.id)
    expect(next.document.fields[0]).toEqual(userField)
    expect(next.document.modifiers[0].field_id).not.toBe(userField.id)
  })
  it('uses real schema limits, dimensionless ratios, and rejects invalid pairs without changing input', () => {
    const dto = createExampleDocument('basic-grid', 'grid'), draft = openLinearSize(dto, phase1aBounds)
    expect(linearSizeGroup(linearCatalog)?.parameters.slice(1).every(item => item.unit === '')).toBe(true)
    draft.values.strength = NaN; expect(() => linearSizeCandidate(draft, linearCatalog)).toThrow()
    draft.values = { ...linearSizeDefaults, min_output: 2, max_output: 1 }
    expect(() => linearSizeCandidate(draft, linearCatalog)).toThrow('最小尺寸比例')
    expect(dto.document.fields).toHaveLength(0)
  })
})
