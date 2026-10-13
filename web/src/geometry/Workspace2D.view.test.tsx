import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Workspace2D } from './Workspace2D'

describe('LIVE 01 workspace view lifecycle', () => {
  it.each([1200, 500, 390])('keeps user zoom/pan on remount at viewport %i, and fits only a new request', width => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width, height: 600 } as DOMRect)
    const onViewChange = vi.fn(), fitHistory = { current: null as number | null }
    const props = { geometry: [], bounds: { min_x: 10, min_y: 20, max_x: 50, max_y: 60, width: 40, height: 40, units: 'mm' as const },
      mmPerUnit: 1, view: { zoom: 28.15, panX: -123, panY: 47 }, onViewChange, fitHistory,
      selectedId: null, onSelect: vi.fn(), canDrag: () => false, onDragCommit: vi.fn(), pendingPreview: null, fitToken: 1 }
    const first = render(<Workspace2D {...props} />)
    expect(onViewChange).toHaveBeenCalledOnce()
    first.unmount(); onViewChange.mockClear()
    const next = render(<Workspace2D {...props} />)
    expect(onViewChange).not.toHaveBeenCalled()
    expect(next.container.querySelector('.workspace-world')?.getAttribute('transform') ?? next.container.querySelector('[transform]')?.getAttribute('transform')).toContain('28.15')
    next.rerender(<Workspace2D {...props} fitToken={2} />)
    expect(onViewChange).toHaveBeenCalledOnce()
    fireEvent.click(next.getByRole('button', { name: '适合窗口' }))
    expect(onViewChange).toHaveBeenCalledTimes(2)
    vi.restoreAllMocks()
  })
})
