import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App'

describe('P0 fixed design workspace', () => {
  it('keeps page scroll locked and assigns independent scroll containers', () => {
    const style = document.createElement('style')
    style.textContent = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8')
    document.head.appendChild(style)
    try {
      const { container } = render(<App />)
      const shell = container.querySelector('.app-shell')!
      const area = container.querySelector('.work-area')!
      const left = container.querySelector('.sidebar')!
      const right = container.querySelector('.inspector')!
      const workspace = container.querySelector('.workspace')!
      const canvas = container.querySelector('.canvas-stage')!
      const modes = container.querySelector('.mode-bar')!
      expect(getComputedStyle(document.body).overflow).toBe('hidden')
      expect(getComputedStyle(shell).overflow).toBe('hidden')
      expect(getComputedStyle(area).overflow).toBe('hidden')
      expect(getComputedStyle(left).overflowY).toBe('scroll')
      expect(getComputedStyle(right).overflowY).toBe('scroll')
      expect(getComputedStyle(workspace).overflow).toBe('hidden')
      expect(getComputedStyle(canvas).minHeight).toBe('0px')
      expect(getComputedStyle(modes).flex).toBe('0 0 72px')
      expect(container.querySelector('.layout-parameters')).toBeNull()
    } finally {
      style.remove()
    }
  })
})
