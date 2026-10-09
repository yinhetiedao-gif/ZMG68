import { describe, expect, it } from 'vitest'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { linearCatalog } from '../test/linearSizeFixture'
import { openRadialSize, radialSizeCandidate, radialSizeLayer } from './radialSize'
import { linearSizeCandidate, openLinearSize } from './linearSize'
import { STACK_KEY } from './selectors'
import type { ParameterCatalog } from './parameterSchema'
const catalog: ParameterCatalog = { ...linearCatalog, definitions: { ...linearCatalog.definitions, field: {
  ...linearCatalog.definitions.field, ring: { label: '环形场坐标Schema', parameters: ['center_x', 'center_y', 'radius'].map(id => ({
    id, label: id, type: 'number', default: 1, value: 1, min: id === 'radius' ? 0 : -10000, max: 10000, step: .1, unit: 'mm', options: [],
  })) },
} } }
describe('legacy radial size shortcut without layout conversion or new algorithms', () => {
  it('keeps Grid and Linear, adds one owned ordered radial layer, converts mm once and updates it', () => {
    const source = createExampleDocument('basic-grid', 'radial'); source.document.canvas.mm_per_unit = .5
    const dto = linearSizeCandidate(openLinearSize(source, phase1aBounds), catalog), before = JSON.stringify(dto)
    const draft = openRadialSize(dto, phase1aBounds), next = radialSizeCandidate(draft, catalog)
    expect(draft.values.center_x).toBe(40); expect(draft.values.center_y).toBe(50)
    expect(radialSizeLayer(next)?.parameters).toMatchObject({ center_x: 80, center_y: 100, min_scale: 1.2, max_scale: .6, mode: 'radial' })
    expect(next.document.fields).toBe(dto.document.fields); expect(next.document.modifiers).toBe(dto.document.modifiers)
    expect(next.document.elements).toBe(dto.document.elements); expect(next.document_revision).toBe(dto.document_revision)
    expect(JSON.stringify(dto)).toBe(before)
    const edit = openRadialSize(JSON.parse(JSON.stringify(next)), phase1aBounds); edit.values.center_x = 45
    const updated = radialSizeCandidate(edit, catalog)
    expect((updated.document.metadata[STACK_KEY] as any).modifiers).toHaveLength(1)
    expect(radialSizeLayer(updated)?.id).toBe(radialSizeLayer(next)?.id)
  })
  it('rejects invalid radii and disabled/non-neutral legacy stacks rather than silently transforming other effects', () => {
    const dto = createExampleDocument('basic-grid', 'r'), draft = openRadialSize(dto, phase1aBounds)
    draft.values.radius = 0; expect(() => radialSizeCandidate(draft, catalog)).toThrow()
    draft.values.radius = 10; dto.document.metadata[STACK_KEY] = { enabled: false }
    expect(() => radialSizeCandidate(openRadialSize(dto, phase1aBounds), catalog)).toThrow('已停用')
    dto.document.metadata[STACK_KEY] = { enabled: true, size_field: { mode: 'radial', min_scale: .5 } }
    expect(() => radialSizeCandidate(openRadialSize(dto, phase1aBounds), catalog)).toThrow('旧兼容')
  })
})
