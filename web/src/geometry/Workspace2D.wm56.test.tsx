import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Workspace2D } from './Workspace2D'
import type { FinalGeometry } from '../model/types'

const dot: FinalGeometry = {
  id: 'source-dot-7', type: 'circle', x: 10, y: 10, width: 4, height: 4,
  rotation: 0, units: 'mm', style: { fill: '#000' },
}

describe('WM5.6 direct drag rendering', () => {
  it('retains the last valid geometry during drag and removes the transient transform after evaluate', () => {
    const onDragCommit = vi.fn()
    const props = {
      geometry: [dot], bounds: null, mmPerUnit: 1,
      view: { zoom: 1, panX: 0, panY: 0 }, onViewChange: vi.fn(),
      selectedId: 'source-dot-7', onSelect: vi.fn(), canDrag: () => true,
      onDragCommit, pendingPreview: null, fitToken: 0,
    }
    const { container, rerender } = render(<Workspace2D {...props} />)
    const canvas = container.querySelector('svg')!
    const node = container.querySelector<SVGGElement>('[data-element-id="source-dot-7"]')!
    fireEvent.pointerDown(node, { button: 0, pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 14, clientY: 10 })
    expect(onDragCommit).not.toHaveBeenCalled()
    expect(container.querySelectorAll('[data-element-id]')).toHaveLength(1)
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: 14, clientY: 10 })
    expect(onDragCommit).toHaveBeenCalledOnce()
    expect(onDragCommit).toHaveBeenCalledWith('source-dot-7', 4, 0)
    expect(node.getAttribute('transform')).toBe('translate(4 0)')

    // A fast backend response may be batched with pointerup. React never
    // observes pendingPreview in that case, so it cannot diff away a DOM-only
    // transform unless the interaction layer explicitly reconciles it.
    rerender(<Workspace2D {...props} geometry={[{ ...dot, x: 14 }]} />)
    expect(node.getAttribute('transform')).toBeNull()
    expect(node.querySelector('circle')?.getAttribute('cx')).toBe('14')
    expect(container.querySelectorAll('[data-element-id]')).toHaveLength(1)
  })
})
