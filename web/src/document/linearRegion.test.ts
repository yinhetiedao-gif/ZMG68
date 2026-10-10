import { describe, it, expect } from 'vitest'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { linearCatalog } from '../test/linearSizeFixture'
import { openLinearSize, linearSizeCandidate, linearSizeOwner } from './linearSize'
import { gradientHandleChange, gradientMarkers, type GradientControl } from '../geometry/gradientControls'
const catalog = structuredClone(linearCatalog)
catalog.definitions.field.ring = { label: '范围', parameters: ['center_x','center_y','radius'].map(id => ({
  id, label: id, type: 'number', default: 1, value: 1, min: id === 'radius' ? .01 : -10000,
  max: 10000, step: .1, unit: 'mm', options: [],
})) }
describe('finite linear scope uses existing draft, references and world units', () => {
  it('persists local scope once, restores it, and returns to legacy global without leaking the rectangle', () => {
    const dto = createExampleDocument('basic-grid','local'); dto.document.canvas.mm_per_unit = .5
    const draft = openLinearSize(dto, phase1aBounds)
    expect(draft.values.scope_mode).toBe('global')
    Object.assign(draft.values, { scope_mode: 'local', center_x: 40, center_y: 50, length: 20, width: 10, feather: 1 })
    const next = linearSizeCandidate(draft,catalog), owner = linearSizeOwner(next)!
    expect(owner.field.parameters).toEqual({ angle: 0, start: 60, end: 100 })
    expect(owner.modifier.region).toEqual({ center_x: 80, center_y: 100, length: 40, width: 20, feather: 2, angle: 0 })
    expect(next.document_revision).toBe(dto.document_revision)
    expect(next.document.elements).toBe(dto.document.elements)
    const restored = openLinearSize(JSON.parse(JSON.stringify(next)), phase1aBounds)
    expect(restored.values).toEqual(draft.values)
    restored.values.scope_mode = 'global'
    const global = linearSizeCandidate(restored,catalog)
    expect(global.document.fields).toHaveLength(1); expect(global.document.modifiers).toHaveLength(1)
    expect(JSON.parse(JSON.stringify(global)).document.modifiers[0].region).toBeUndefined()
    expect(openLinearSize(global,phase1aBounds).values.scope_mode).toBe('global')
  })
  it('rejects invalid finite rectangle and oversized feather before touching the source', () => {
    const dto = createExampleDocument('basic-grid','invalid'), draft = openLinearSize(dto,phase1aBounds), before = JSON.stringify(dto)
    draft.values.scope_mode = 'local'; draft.values.length = 0
    expect(() => linearSizeCandidate(draft,catalog)).toThrow()
    draft.values.length = 10; draft.values.feather = 6
    expect(() => linearSizeCandidate(draft,catalog)).toThrow('过渡')
    expect(JSON.stringify(dto)).toBe(before)
  })
  it('two endpoints, center and transverse handle edit the same numeric draft without camera/unit changes', () => {
    const control: GradientControl = { kind:'linear', bounds: phase1aBounds,
      values: { scope_mode:'local', angle:0, center_x:40,center_y:50,length:20,width:10 } }
    expect(gradientMarkers(control)).toEqual({center:{x:40,y:50},point:{x:50,y:50}})
    expect(gradientHandleChange(control,'end',{x:60,y:50})).toEqual({center_x:45,center_y:50,length:30,angle:0})
    expect(gradientHandleChange(control,'start',{x:20,y:50})).toEqual({center_x:35,center_y:50,length:30,angle:0})
    expect(gradientHandleChange(control,'center',{x:45,y:55})).toEqual({center_x:45,center_y:55})
    expect(gradientHandleChange(control,'width',{x:40,y:60})).toEqual({width:20})
  })
})
