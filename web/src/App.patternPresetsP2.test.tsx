import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { createExampleDocument } from './examples/catalog'
import * as drafts from './draft/localDraft'
import base from './test/sizeFieldCatalog.json'
import design from './test/designCatalog.json'
import type { PatternDocumentDTO } from './model/types'
import { patternPresets } from './document/patternPresets'

function backend() {
  const requests: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    const reply = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: { ...base, definitions: { ...base.definitions, design } } })
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; requests.push(dto)
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })),
      bounds_mm: { min_x: 4.3, min_y: 4.3, max_x: 55.7, max_y: 55.7, width: 51.4, height: 51.4, units: 'mm' }, warnings: [] })
  }))
  return requests
}
const cases = [
  ['local-breath', '局部呼吸', '局部尺寸倍率', .85],
  ['coral-grains', '珊瑚微粒', '尺度 (mm)', 19],
  ['ripple-center', '涟心扩散', '影响半径 (mm)', 20],
  ['vortex-scales', '旋涡鳞纹', '螺旋密度', 1.6],
] as const
describe('P2 cards use one candidate/history and protected-return pipeline', () => {
  it.each(cases)('%s edits, cancels, applies once, restores and returns the exact original', async (id, title, label, value) => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    const original = createExampleDocument('basic-grid', 'user-original')
    delete original.document.metadata['xiaomang_pattern_lab.example_id']
    original.document.metadata.user_marker = { keep: 'source, height, units' }
    await drafts.saveDraft(original, 'my-work', null)
    const requests = backend(), view = render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await waitFor(() => expect(requests.at(-1)?.document_id).toBe(original.document_id))
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: `创建${title}` }))
    const ready = () => waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    await ready(); const created = requests.at(-1)!
    if (id === 'vortex-scales') {
      expect(screen.getByRole('slider', { name: '相位滑杆' })).toHaveValue('0.15')
      expect(screen.getByText(/分别映射尺寸比例和旋转角度/)).toBeInTheDocument()
    }
    expect(created.document.metadata.web_pattern_preset).toMatchObject({ id })
    expect(created.document_revision).toBe(0)
    const input = screen.getByRole('spinbutton', { name: label })
    fireEvent.change(input, { target: { value } }); fireEvent.blur(input); await ready()
    expect(requests.at(-1)?.document_revision).toBe(0)
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: `编辑${title}` })); await ready()
    const edit = screen.getByRole('spinbutton', { name: label })
    fireEvent.change(edit, { target: { value } }); fireEvent.blur(edit); await ready()
    const count = requests.length
    fireEvent.click(screen.getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests).toHaveLength(count+1))
    const applied = requests.at(-1)!
    expect(applied.document_revision).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)?.document).toEqual(created.document))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(requests.at(-1)?.document).toEqual(applied.document))
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: `编辑${title}` })); await ready()
    fireEvent.click(screen.getByRole('button', { name: '恢复默认' })); await ready()
    expect(requests.at(-1)?.document).toEqual(created.document)
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    await waitFor(async () => expect((await drafts.loadDraft())?.dto.document).toEqual(applied.document))
    view.unmount(); render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(requests.at(-1)?.document).toEqual(original.document))
    expect((await drafts.loadBeforeExampleDraft())?.dto.document).toEqual(applied.document)
  }, 15000)
})
