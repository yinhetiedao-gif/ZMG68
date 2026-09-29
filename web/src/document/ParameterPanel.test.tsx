import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ParameterPanel } from './ParameterPanel'
import { validateParameter, type ParameterGroup } from './parameterSchema'

const group: ParameterGroup = { label: '测试', parameters: [
  { id: 'radius', label: '半径', type: 'number', default: 2, value: 2, min: 0, max: 30, step: 1, unit: 'mm', options: [] },
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

  it('rejects invalid intermediate values and illegal choices', () => {
    expect(validateParameter(group.parameters[1], 2.5)).toBe(false)
    expect(validateParameter(group.parameters[0], Infinity)).toBe(false)
    expect(validateParameter(group.parameters[3], 'c')).toBe(false)
  })

  it('commits a checked boolean and an allowed select value', () => {
    const commit = vi.fn()
    render(<ParameterPanel group={group} values={{ invert: false, mode: 'a' }} onCommit={commit} />)
    fireEvent.click(screen.getByLabelText('反转'))
    fireEvent.change(screen.getByLabelText('模式'), { target: { value: 'b' } })
    expect(commit.mock.calls).toEqual([['invert', true], ['mode', 'b']])
  })
})
