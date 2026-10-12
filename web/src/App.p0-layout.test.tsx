import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App'

describe('P0 fixed design workspace', () => {
  it('keeps page and canvas stable with a single left parameter scroll container', () => {
    const style = document.createElement('style')
    style.textContent = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8')
    document.head.appendChild(style)
    try {
      const { container } = render(<App />)
      const shell = container.querySelector('.app-shell')!
      const area = container.querySelector('.work-area')!
      const left = container.querySelector<HTMLElement>('.sidebar')!
      const right = container.querySelector<HTMLElement>('.inspector')!
      const parameters = container.querySelector<HTMLElement>('.function-panel-scroll')!
      const workspace = container.querySelector('.workspace')!
      const canvas = container.querySelector('.canvas-stage')!
      const modes = container.querySelector('.mode-bar')!
      expect(getComputedStyle(document.body).overflow).toBe('hidden')
      expect(getComputedStyle(shell).overflow).toBe('hidden')
      expect(getComputedStyle(area).overflow).toBe('hidden')
      expect(getComputedStyle(parameters).overflowY).toBe('auto')
      expect(getComputedStyle(left).overflow).toBe('visible')
      expect(getComputedStyle(right).overflow).toBe('visible')
      expect(parameters).toContainElement(left)
      expect(parameters).toContainElement(right)
      expect(getComputedStyle(area).gridTemplateColumns).toBe('340px minmax(0, 1fr)')
      expect(getComputedStyle(container.querySelector('.function-menu')!).gridTemplateColumns).toBe('minmax(0, 1fr)')
      expect(getComputedStyle(workspace).overflow).toBe('hidden')
      expect(getComputedStyle(canvas).minHeight).toBe('0px')
      expect(getComputedStyle(modes).flex).toBe('0 0 72px')
      expect(container.querySelector('.layout-parameters')).toBeNull()
    } finally {
      style.remove()
    }
  })
})
