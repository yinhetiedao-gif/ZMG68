import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Workspace2D } from './Workspace2D'
import { gradientHandleChange, gradientMarkers, type GradientControl } from './gradientControls'
const bounds = { min_x: 10, min_y: 20, max_x: 70, max_y: 60, width: 60, height: 40, units: 'mm' as const }
const radial: GradientControl = { kind: 'radial', bounds, values: { center_x: 40, center_y: 40, radius: 12 } }
const props = { geometry: [], bounds: null, mmPerUnit: .5, view: { zoom: 2, panX: 30, panY: 15 },
  onViewChange: vi.fn(), selectedId: null, onSelect: vi.fn(), canDrag: () => true, onDragCommit: vi.fn(), pendingPreview: null, fitToken: 0 }
describe('gradient editing helpers, not design geometry', () => {
  it('uses positive world-Y/degree convention, with a visual axis only', () => {
    for (const angle of [0, 45, 180]) {
      const control: GradientControl = { kind: 'linear', bounds, values: { angle } }
      const { center, point } = gradientMarkers(control)
      expect(center).toEqual({ x: 40, y: 40 })
      expect(gradientHandleChange(control, 'direction', point).angle).toBeCloseTo(angle)
    }
    expect(gradientHandleChange(radial, 'radius', { x: 43, y: 44 })).toEqual({ radius: 5 })
  })
  it('maps pointer to mm once, isolates pan/selection, and Cancel restores original pending values', () => {
    const change = vi.fn(), editing = vi.fn()
    const { container } = render(<Workspace2D {...props} gradientControl={radial} onGradientChange={change} onEditingChange={editing} />)
    const canvas = container.querySelector('svg')!, center = container.querySelector('[data-gradient-handle="center"]')!
    fireEvent.pointerDown(center, { button: 0, pointerId: 1, clientX: 110, clientY: 95 })
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 130, clientY: 105 })
    expect(change).toHaveBeenLastCalledWith({ center_x: 50, center_y: 45 })
    expect(props.onSelect).not.toHaveBeenCalled(); expect(props.onViewChange).not.toHaveBeenCalled()
    expect(props.onDragCommit).not.toHaveBeenCalled()
    fireEvent.pointerCancel(canvas)
    expect(change).toHaveBeenLastCalledWith(radial.values); expect(editing).toHaveBeenLastCalledWith(false)
    fireEvent.pointerMove(canvas, { clientX: 160, clientY: 120 })
    expect(change).toHaveBeenCalledTimes(2)
    expect(container.querySelectorAll('[data-element-id]')).toHaveLength(0)
  })
  it('pointerup leaves pending values only; switching effects ends capture without restoring stale configuration', () => {
    const change = vi.fn(), editing = vi.fn()
    const { container, rerender } = render(<Workspace2D {...props} gradientControl={radial} onGradientChange={change} onEditingChange={editing} />)
    const canvas = container.querySelector('svg')!
    fireEvent.pointerDown(container.querySelector('[data-gradient-handle="radius"]')!, { button: 0, pointerId: 1, clientX: 134, clientY: 95 })
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: 150, clientY: 95 })
    expect(change).toHaveBeenLastCalledWith({ radius: 20 }); expect(props.onDragCommit).not.toHaveBeenCalled()
    fireEvent.pointerDown(container.querySelector('[data-gradient-handle="center"]')!, { button: 0, pointerId: 2, clientX: 110, clientY: 95 })
    rerender(<Workspace2D {...props} gradientControl={null} onGradientChange={change} onEditingChange={editing} />)
    fireEvent.pointerCancel(canvas)
    expect(change).toHaveBeenCalledTimes(1); expect(editing).toHaveBeenLastCalledWith(false)
    expect(container.querySelector('[data-gradient-controls]')).toBeNull()
  })
  it('locked reference image stays below helpers and is not a target or a geometry element', () => {
    const { container } = render(<Workspace2D {...props} gradientControl={radial}
      referenceLayer={{ blob: new Blob(), filename: 'guide.png', media_type: 'image/png', url: 'blob:test',
        x_mm: 40, y_mm: 40, width_mm: 60, height_mm: 40, rotation_deg: 0, opacity: .3, visible: true, locked: true }} />)
    expect(container.querySelector('image')).toHaveAttribute('pointer-events', 'none')
    expect(container.querySelectorAll('[data-element-id]')).toHaveLength(0)
    expect(container.querySelectorAll('[data-gradient-handle]')).toHaveLength(2)
  })
})
