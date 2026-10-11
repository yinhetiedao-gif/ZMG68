import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { App } from './App'
import base from './test/sizeFieldCatalog.json'
import design from './test/designCatalog.json'
import type { PatternDocumentDTO } from './model/types'
const reply = (v: unknown) => new Response(JSON.stringify(v), { status: 200, headers: { 'Content-Type': 'application/json' } })
async function open() {
  const requests: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: { ...base, definitions: { ...base.definitions, design } } })
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; requests.push(dto)
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })), bounds_mm: { min_x: 0, min_y: 0, max_x: 60, max_y: 60, width: 60, height: 60, units: 'mm' }, warnings: [] })
  }))
  render(<App />); await screen.findByText('Backend Online')
  fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '图案控制 · 排列/形状/随机/画板' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '图案控制 · 排列/形状/随机/画板' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
  return requests
}
describe('public design panel shares candidate lifecycle without fake geometry commits', () => {
  it('grid/unit-only changes leave revision/history/result eligibility unchanged', async () => {
    const requests = await open(), count = requests.length, revision = requests.at(-1)!.document_revision
    expect(screen.getByRole('button', { name: '下载设计SVG' })).toBeEnabled()
    fireEvent.click(screen.getByLabelText('显示网格'))
    fireEvent.change(screen.getByLabelText('显示单位'), { target: { value: 'cm' } })
    expect(screen.getByRole('button', { name: '下载设计SVG' })).toBeEnabled()
    expect(requests.length).toBe(count)
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: '应用效果' })).not.toBeInTheDocument())
    expect(requests.length).toBe(count); expect(requests.at(-1)!.document_revision).toBe(revision)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
  })
  it('a real shape edit blocks old exports, applies once and Undo restores source without fields', async () => {
    const requests = await open(), revision = requests.at(-1)!.document_revision
    const input = screen.getByRole('spinbutton', { name: '单元尺寸 (%)' })
    fireEvent.focus(input); fireEvent.change(input, { target: { value: '125' } }); fireEvent.blur(input)
    await waitFor(() => expect(requests.at(-1)!.document.metadata.web_design_controls).toHaveProperty('size_percent', 125))
    expect(screen.getByRole('button', { name: '下载透明PNG' })).toBeDisabled()
    const count = requests.length; await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests.at(-1)!.document_revision).toBe(revision + 1)); expect(requests.length).toBe(count + 1)
    expect(requests.at(-1)!.document.fields).toHaveLength(0); expect(requests.at(-1)!.document.modifiers).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)!.document_revision).toBe(revision + 2))
    expect(requests.at(-1)!.document.metadata.web_design_controls).toBeUndefined()
  })
})
