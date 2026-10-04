import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ParameterPanel } from './ParameterPanel'
import { recommendedSlider, validateParameter, type ParameterGroup } from './parameterSchema'

const group: ParameterGroup = { label: '测试', parameters: [
  { id: 'radius', label: '半径', type: 'number', default: 2, value: 2, min: 0, max: 30, step: 1, unit: 'mm', options: [] },
  { id: 'wavelength', label: '波长', type: 'number', default: 50, value: 50, min: 0.01, max: 10000, step: 0.1,
    slider_min: 1, slider_max: 300, slider_step: 0.1, unit: 'mm', options: [] },
  { id: 'rows', label: '行数', type: 'integer', default: 4, value: 4, min: 1, max: 20, step: 1, unit: '', options: [] },
  { id: 'invert', label: '反转', type: 'boolean', default: false, value: false, min: null, max: null, step: null, unit: '', options: [] },
  { id: 'mode', label: '模式', type: 'select', default: 'a', value: 'a', min: null, max: null, step: null,
    unit: '', options: [{ value: 'a', label: '甲' }, { value: 'b', label: '乙' }] },
] }

describe('Python-authored generic parameter renderer', () => {
  it('renders numeric, integer, boolean and select with units and bounds', () => {
    render(<ParameterPanel group={group} values={{ radius: 2, rows: 4, invert: false, mode: 'a' }} onCommit={vi.fn()} />)
    expect(screen.getByLabelText('半径 (mm)')).toHaveAttribute('max', '30')
    expect(screen.getByLabelText('行数')).toHaveAttribute('step', '1')
    expect(screen.getByLabelText('反转')).toHaveAttribute('type', 'checkbox')
    expect(screen.getByLabelText('模式')).toHaveValue('a')
  })

  it('keeps slider transient and commits once on release', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ radius: 2 }} onCommit={commit} />)
    const slider = screen.getByLabelText('半径滑杆')
    fireEvent.change(slider, { target: { value: '12' } })
    expect(commit).not.toHaveBeenCalled()
    fireEvent.pointerUp(slider)
    expect(commit).toHaveBeenCalledExactlyOnceWith('radius', 12)
  })

  it('limits only the mm slider to 1–300 while retaining a legal value above 300', () => {
    const commit = vi.fn()
    const { rerender } = render(<ParameterPanel group={group} values={{ wavelength: 500 }} onCommit={commit} />)
    const slider = screen.getByLabelText('波长滑杆')
    const numeric = screen.getByLabelText('波长 (mm)')
    expect(slider).toHaveAttribute('min', '1')
    expect(slider).toHaveAttribute('max', '300')
    expect(slider).toHaveValue('300')
    expect(numeric).toHaveAttribute('min', '0.01')
    expect(numeric).toHaveAttribute('max', '10000')
    expect(numeric).toHaveValue(500)
    expect(screen.getByText(/超出推荐调节范围/)).toBeVisible()
    fireEvent.pointerUp(slider)
    expect(commit).not.toHaveBeenCalled()
    fireEvent.change(numeric, { target: { value: '750' } })
    fireEvent.blur(numeric)
    expect(commit).toHaveBeenCalledExactlyOnceWith('wavelength', 750)
    rerender(<ParameterPanel group={group} values={{ wavelength: 750 }} onCommit={commit} />)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(750)
    expect(screen.getByLabelText('波长滑杆')).toHaveValue('300')
    fireEvent.click(screen.getByRole('button', { name: '重置波长' }))
    expect(commit.mock.calls).toEqual([['wavelength', 750], ['wavelength', 50]])
  })

  it('commits a mm slider drag only on release and leaves other units unchanged', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ wavelength: 50 }} onCommit={commit} />)
    const slider = screen.getByLabelText('波长滑杆')
    fireEvent.change(slider, { target: { value: '250' } })
    expect(commit).not.toHaveBeenCalled()
    fireEvent.pointerUp(slider)
    expect(commit).toHaveBeenCalledExactlyOnceWith('wavelength', 250)
    expect(recommendedSlider({ ...group.parameters[1], unit: '°', slider_min: -180, slider_max: 180, slider_step: 1 }))
      .toEqual({ min: -180, max: 180, step: 1 })
  })

  it('rejects invalid intermediate values and illegal choices', () => {
    expect(validateParameter(group.parameters[2], 2.5)).toBe(false)
    expect(validateParameter(group.parameters[0], Infinity)).toBe(false)
    expect(validateParameter(group.parameters[4], 'c')).toBe(false)
  })

  it('commits a checked boolean and an allowed select value', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ invert: false, mode: 'a' }} onCommit={commit} />)
    fireEvent.click(screen.getByLabelText('反转'))
    fireEvent.change(screen.getByLabelText('模式'), { target: { value: 'b' } })
    expect(commit.mock.calls).toEqual([['invert', true], ['mode', 'b']])
  })

  it('shows concise numbers but exposes full precision on focus without rounding the committed value', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ radius: 3.842193847263 }} onCommit={commit} />)
    const numeric = screen.getByLabelText('半径 (mm)')
    expect(numeric).toHaveValue(3.842)
    fireEvent.focus(numeric)
    expect(numeric).toHaveValue(3.842193847263)
    fireEvent.blur(numeric)
    expect(commit).not.toHaveBeenCalled()
    expect(numeric).toHaveValue(3.842)
  })

  it('resets numeric, boolean and select values from the schema without committing a pending draft first', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ radius: 12, invert: true, mode: 'b' }} onCommit={commit} />)
    fireEvent.change(screen.getByLabelText('半径 (mm)'), { target: { value: '16' } })
    fireEvent.pointerDown(screen.getByRole('button', { name: '重置半径' }))
    fireEvent.click(screen.getByRole('button', { name: '重置半径' }))
    fireEvent.blur(screen.getByLabelText('半径 (mm)'))
    fireEvent.click(screen.getByRole('button', { name: '重置反转' }))
    fireEvent.click(screen.getByRole('button', { name: '重置模式' }))
    expect(commit.mock.calls).toEqual([['radius', 2], ['invert', false], ['mode', 'a']])
  })
})
