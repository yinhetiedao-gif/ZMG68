import { fireEvent, render, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PatternPresetPicker } from './PatternPresetPicker'
import { patternPresets } from './patternPresets'

describe('P4-C1 real preset thumbnail presentation', () => {
  it('keeps eight vector thumbnails and original create/apply/edit callbacks', () => {
    const onCreate = vi.fn(), onApply = vi.fn(), onEdit = vi.fn()
    const { container } = render(<PatternPresetPicker onCreate={onCreate} onApply={onApply} onEdit={onEdit}
      currentId="spectrum-fade" createDisabled={false} applyDisabled={false} />)
    const cards = [...container.querySelectorAll('article')]
    expect(cards).toHaveLength(8)
    cards.forEach((card, index) => {
      const preset = patternPresets[index], image = card.querySelector('img')!
      expect(image.src).toContain(`${preset.id}.svg`)
      expect(image).toHaveAttribute('width', '92'); expect(image).toHaveAttribute('height', '92')
      expect(card.querySelector('.pattern-preset-copy')).not.toContainElement(card.querySelector('.pattern-preset-actions'))
      fireEvent.click(within(card as HTMLElement).getByRole('button', { name: `创建${preset.title}` }))
      expect(onCreate).toHaveBeenLastCalledWith(preset.id)
      if (preset.supportsCurrent) {
        fireEvent.click(within(card as HTMLElement).getByRole('button', { name: `应用${preset.title}效果` }))
        expect(onApply).toHaveBeenLastCalledWith(preset.id)
      }
    })
    fireEvent.click(within(cards[1] as HTMLElement).getByRole('button', { name: '编辑光谱渐隐' }))
    expect(onEdit).toHaveBeenCalledWith('spectrum-fade')
  })
  it('retains disabled protection instead of making unavailable operations clickable', () => {
    const onCreate = vi.fn(), onApply = vi.fn()
    const { container } = render(<PatternPresetPicker onCreate={onCreate} onApply={onApply} onEdit={vi.fn()}
      currentId={null} createDisabled applyDisabled />)
    expect([...container.querySelectorAll('button')].every(button => button.disabled)).toBe(true)
    fireEvent.click(container.querySelector('button')!)
    expect(onCreate).not.toHaveBeenCalled(); expect(onApply).not.toHaveBeenCalled()
  })
})
