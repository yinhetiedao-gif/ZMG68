import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { InspectorSection } from './InspectorSection'

describe('shared visual disclosure', () => {
  it('keeps the accessible title, a right-side chevron and the same controls when folded', () => {
    const view = render(<InspectorSection title="形状与单元" label="单元尺寸设置" icon="shape"><input aria-label="单元大小" defaultValue="4" /></InspectorSection>)
    const toggle = screen.getByRole('button', { name: '形状与单元' })
    const input = screen.getByRole('textbox', { name: '单元大小' })
    expect(toggle.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(toggle.lastElementChild).toHaveClass('disclosure-chevron')
    expect(toggle.lastElementChild).toHaveAttribute('aria-hidden', 'true')
    fireEvent.change(input, { target: { value: '7' } })
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('textbox', { name: '单元大小' })).toBeNull()
    fireEvent.click(toggle)
    expect(screen.getByRole('textbox', { name: '单元大小' })).toBe(input)
    expect(input).toHaveValue('7')
    expect(view.container.querySelectorAll('.panel-icon')).toHaveLength(2)
  })
  it('does not add a decorative leading icon to secondary parameters', () => {
    render(<InspectorSection title="布点方式" label="单元布点设置" defaultExpanded={false}>设置</InspectorSection>)
    const toggle = screen.getByRole('button', { name: '布点方式' })
    expect(toggle.firstElementChild).toHaveClass('section-title')
    expect(toggle.querySelectorAll('.panel-icon')).toHaveLength(1)
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })
  it('keeps the existing controlled accordion callback instead of introducing a second state', () => {
    const change = vi.fn()
    const view = render(<InspectorSection title="高度与变化" label="直接高度控制" icon="height" expanded={false} onExpandedChange={change}>设置</InspectorSection>)
    fireEvent.click(screen.getByRole('button', { name: '高度与变化' }))
    expect(change).toHaveBeenCalledExactlyOnceWith(true)
    expect(screen.getByRole('button', { name: '高度与变化' })).toHaveAttribute('aria-expanded', 'false')
    view.rerender(<InspectorSection title="高度与变化" label="直接高度控制" icon="height" expanded onExpandedChange={change}>设置</InspectorSection>)
    expect(screen.getByRole('button', { name: '高度与变化' })).toHaveAttribute('aria-expanded', 'true')
  })
})
