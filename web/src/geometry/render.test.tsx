import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { geometryShape } from './render'
import type { FinalGeometry } from '../model/types'

const base: FinalGeometry = {
  id: 'element', type: 'circle', x: 20, y: 30, width: 10, height: 10,
  rotation: 0, units: 'mm', style: { fill: '#000000', stroke: 'none' },
}

describe('WM2 final geometry SVG renderer', () => {
  it('renders circle, ellipse and rect in world mm', () => {
    expect(renderToStaticMarkup(geometryShape(base, 1))).toContain('cx="20"')
    expect(renderToStaticMarkup(geometryShape({ ...base, type: 'ellipse', height: 6 }, 1))).toContain('ry="3"')
    expect(renderToStaticMarkup(geometryShape({ ...base, type: 'rect' }, 1))).toContain('x="15"')
  })

  it('preserves a filled hole using the official evenodd path style', () => {
    const path = { ...base, type: 'filled_region' as const,
      path_data: 'M0 0H10V10H0Z M3 3H7V7H3Z',
      path_data_coordinate_system: 'element_local' as const,
      base_x: 5, base_y: 5, base_width: 10, base_height: 10,
      style: { fill: '#000', stroke: 'red', 'fill-rule': 'evenodd' },
    }
    const html = renderToStaticMarkup(geometryShape(path, 1))
    expect(html).toContain('fill-rule="evenodd"')
    expect(html).toContain('stroke="none"')
    expect(html).toContain('M3 3H7V7H3Z')
  })

  it('keeps path local coordinates separate from world millimetre placement', () => {
    const path = { ...base, type: 'path' as const, x: 20, y: 30, width: 10, height: 10,
      path_data: 'M-0.5 -0.5L0.5 -0.5L0.5 0.5Z', path_data_coordinate_system: 'element_local' as const,
      base_x: 0, base_y: 0, base_width: 2, base_height: 2,
    }
    const html = renderToStaticMarkup(geometryShape(path, 2))
    expect(html).toContain('scale(2)')
    expect(html).toContain('translate(10 15)')
    expect(html).toContain('M-0.5 -0.5')
  })
})
