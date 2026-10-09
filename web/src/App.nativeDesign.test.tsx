import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response
function backend() {
  const evaluated: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm' })
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; evaluated.push(dto)
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })), bounds_mm: null, warnings: [] })
  }))
  return evaluated
}
describe('native design context and compatibility', () => {
  it('offers two modes, appends shapes with one undo and edits through the existing element inspector', async () => {
    const evaluated = backend(); render(<App />); await screen.findByText('Backend Online')
    expect(within(screen.getByRole('navigation', { name: '工作模式' })).getAllByRole('button')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: '使用推荐' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '＋ 添加圆形' }))
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: '宽度 mm' })).toBeEnabled())
    expect(evaluated.at(-1)?.document.elements).toHaveLength(1)
    expect(screen.queryByRole('region', { name: '参数场' })).toBeNull()
    const width = screen.getByRole('spinbutton', { name: '宽度 mm' })
    fireEvent.change(width, { target: { value: '12' } }); fireEvent.blur(width)
    await waitFor(() => expect(evaluated).toHaveLength(2))
    expect(evaluated.at(-1)?.document.elements[0].width).toBe(12)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluated.at(-1)?.document.elements[0].width).toBe(10))
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluated.at(-1)?.document.elements).toHaveLength(0))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(evaluated.at(-1)?.document.elements).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: '＋ 添加椭圆' }))
    await waitFor(() => expect(evaluated.at(-1)?.document.elements).toHaveLength(2))
    expect(evaluated.at(-1)?.document.elements.map(e => e.type)).toEqual(['circle', 'ellipse'])
    fireEvent.click(screen.getByRole('button', { name: '参数场与效果' }))
    expect(screen.getByRole('region', { name: '参数场' })).toBeVisible()
    expect(screen.queryByRole('region', { name: '元素变换' })).toBeNull()
  })
  it('maps a legacy link to the retained manufacture/preview area without fabricating a result', async () => {
    backend(); window.history.replaceState(null, '', '/?mode=preview')
    render(<App />); await screen.findByText('Backend Online')
    expect(screen.getByRole('button', { name: /制造 Manufacture/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: /3D Preview/ })).toBeNull()
    window.history.replaceState(null, '', '/')
  })
})
