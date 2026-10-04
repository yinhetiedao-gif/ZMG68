import { describe, expect, it } from 'vitest'
import basicGrid from '../examples/fixtures/basic-grid.pattern.json'
import { prepareProject } from '../model/project'
import type { BoundsMM } from '../model/types'
import { confirmUniformRealSize, realSizeConfirmed } from './realSize'

const bounds: BoundsMM = { min_x: 10, min_y: 10, max_x: 50, max_y: 50, width: 40, height: 40, units: 'mm' }

describe('real-size confirmation through existing millimetre mapping', () => {
  it('commits one revision, preserves project geometry and precision, and survives serialization', () => {
    const source = prepareProject(JSON.stringify(basicGrid), 'grid').dto
    const next = confirmUniformRealSize(source, bounds, 60, 60)
    expect(next.document_revision).toBe(1)
    expect(next.document.canvas.mm_per_unit).toBe(1.5)
    expect(next.document.elements).toEqual(source.document.elements)
    const finalBounds = { ...bounds, width: 60, height: 60 }
    expect(realSizeConfirmed(next, finalBounds)).toBe(true)
    expect(realSizeConfirmed(next, { ...finalBounds, width: 61 })).toBe(false)
    expect(realSizeConfirmed(JSON.parse(JSON.stringify(next)), finalBounds)).toBe(true)
  })

  it('rejects non-uniform or invalid sizing instead of lying about the STL', () => {
    const source = prepareProject(JSON.stringify(basicGrid), 'grid').dto
    expect(() => confirmUniformRealSize(source, bounds, 60, 50)).toThrow(/等比尺寸/)
    expect(() => confirmUniformRealSize(source, bounds, Number.NaN, 60)).toThrow(/有限的正数/)
  })
})
