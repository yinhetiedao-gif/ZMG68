import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RealSizePanel } from './RealSizePanel'

describe('real size display precision', () => {
  it('shows concise values at rest and full values while editing without changing the measurement', () => {
    const onConfirm = vi.fn()
    render(<RealSizePanel document={null} bounds={{ min_x: 0, min_y: 0, max_x: 3.842193847263, max_y: 60.25, width: 3.842193847263, height: 60.25, units: 'mm' }} disabled={false} onConfirm={onConfirm} />)
    const width = screen.getByRole('spinbutton', { name: '真实宽度 mm' }) as HTMLInputElement
    expect(width.value).toBe('3.842')
    fireEvent.focus(width)
    expect(width.value).toBe('3.842193847263')
    fireEvent.blur(width)
    expect(width.value).toBe('3.842')
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
