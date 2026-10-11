import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { linearCatalog } from './test/linearSizeFixture'
import type { PatternDocumentDTO } from './model/types'
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response
function backend() {
  const evaluated: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: linearCatalog })
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; evaluated.push(dto)
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })),
      bounds_mm: { min_x: 0, min_y: 0, max_x: 40, max_y: 40, width: 40, height: 40, units: 'mm' }, warnings: [] })
  }))
  return evaluated
}
describe('linear size shortcut App lifecycle', () => {
  it('cannot apply an old candidate after Undo changes the formal document; Cancel never restores the old snapshot', async () => {
    const requests = backend(); render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '撤销' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)?.document.modifiers).toHaveLength(0))
    expect(screen.getByRole('button', { name: '应用效果' })).toBeDisabled()
    expect(screen.getByText(/正式设计已变化，请重新打开效果/)).toBeVisible()
    const count = requests.length
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(requests).toHaveLength(count); expect(requests.at(-1)?.document.modifiers).toHaveLength(0)
  })
  it('candidate and Cancel do not commit; Apply once, Undo/Redo and reopen update one modifier', async () => {
    const requests = backend(); render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    const base = requests.at(-1)!
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    expect(requests.at(-1)?.document_revision).toBe(base.document_revision)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const count = requests.length
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests).toHaveLength(count + 1))
    expect(requests.at(-1)?.document_revision).toBe(base.document_revision + 1)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)?.document.modifiers).toHaveLength(0))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(requests.at(-1)?.document.modifiers).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const angle = screen.getByRole('spinbutton', { name: '渐变方向' })
    fireEvent.change(angle, { target: { value: 45 } }); fireEvent.blur(angle)
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests.at(-1)?.document.fields[0].parameters).toHaveProperty('angle', 45))
    expect(requests.at(-1)?.document.modifiers).toHaveLength(1)
  })
})
