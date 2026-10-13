import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { createExampleDocument } from './examples/catalog'
import { updateGrid } from './document/editor'
import { initialLayoutDraft } from './document/layoutDraft'
import { patternPresets } from './document/patternPresets'
import type { ParameterCatalog } from './document/parameterSchema'
import base from './test/sizeFieldCatalog.json'
import design from './test/designCatalog.json'
import type { PatternDocumentDTO } from './model/types'
import * as drafts from './draft/localDraft'
const catalog = { ...base, definitions: { ...base.definitions, design } }
function backend() {
  const requests: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    const reply = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog })
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; requests.push(dto)
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })),
      bounds_mm: { min_x: 4.3, min_y: 4.3, max_x: 55.7, max_y: 55.7, width: 51.4, height: 51.4, units: 'mm' }, warnings: [] })
  }))
  return requests
}
async function picker() {
  render(<App />); await screen.findByText('Backend Online')
  fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
}
describe('pattern presets share the protected project and candidate workflow', () => {
  it('creates Wave, candidate/Cancel do not commit; Apply once and Undo/Redo preserve full recipe', async () => {
    const requests = backend(); await picker()
    expect(screen.queryByRole('button', { name: '应用精密错列效果' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '创建斜向潮汐' }))
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: '波长 (mm)' })).toHaveValue(23))
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: '编辑斜向潮汐' }))
    const wave = await screen.findByRole('spinbutton', { name: '波长 (mm)' })
    fireEvent.change(wave, { target: { value: 31 } }); fireEvent.blur(wave)
    await waitFor(() => expect(requests.at(-1)?.document.fields[0].parameters).toHaveProperty('wavelength', 31))
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    expect(requests.at(-1)?.document_revision).toBe(0)
    const count = requests.length; fireEvent.click(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests).toHaveLength(count + 1)); expect(requests.at(-1)?.document_revision).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)?.document.fields[0].parameters).toHaveProperty('wavelength', 23))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(requests.at(-1)?.document.fields[0].parameters).toHaveProperty('wavelength', 31))
    expect(requests.at(-1)?.document.modifiers).toHaveLength(1)
  })
  it('save failure does not create a replacement project or apply an effect', async () => {
    const requests = backend(); await picker()
    fireEvent.click(screen.getByRole('button', { name: '创建光谱渐隐' }))
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    await waitFor(() => expect(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` })).toBeEnabled())
    const save = vi.spyOn(drafts, 'saveDraft').mockRejectedValue(new Error('IndexedDB write blocked'))
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    const count = requests.length, id = requests.at(-1)?.document_id
    fireEvent.click(screen.getByRole('button', { name: '创建精密错列' }))
    await screen.findByText(/当前作品保存失败，已取消切换/)
    expect(requests.length).toBe(count); expect(requests.at(-1)?.document_id).toBe(id)
    expect(screen.getByRole('button', { name: '创建精密错列' })).toBeEnabled()
    save.mockRestore()
  })

  it.each(patternPresets.filter(p => ['precision-stagger', 'spectrum-fade', 'diagonal-tide'].includes(p.id)))('$title can become custom and still return the exact original, including pending layout, after refresh', async preset => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    const original = createExampleDocument('basic-grid', 'my-original')
    delete original.document.metadata['xiaomang_pattern_lab.example_id']
    original.document.metadata.user_marker = { keep: 'unsaved committed edit', seed: 77 }
    const pending = { ...initialLayoutDraft(original), changed: true,
      proposal: updateGrid(original, 'rows', 4, catalog as ParameterCatalog) }
    const display = { unit: 'cm' as const, grid: true, pngWidth: 1200 }
    await drafts.saveDraft(original, 'my-original.svg', null,
      { pending_layout: pending, example_session_active: false, design_display: display })
    const requests = backend(), view = render(<App />)
    await screen.findByText('Backend Online')
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await waitFor(() => expect(requests.at(-1)?.document_id).toBe(original.document_id))
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: `创建${preset.title}` }))
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    const recipe = requests.at(-1)!
    expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled()
    expect((await drafts.loadBeforeExampleDraft())?.dto).toEqual(original)
    fireEvent.click(screen.getByRole('button', { name: '高级参数与影响区' }))
    if (!preset.field) fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    fireEvent.change(screen.getByLabelText('变化方式', { exact: true }), { target: { value: 'stripe' } })
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    fireEvent.change(screen.getByLabelText('变化方式', { exact: true }), { target: { value: 'stripe' } })
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' }))
    await waitFor(() => expect(requests.at(-1)?.document_revision).toBe(recipe.document_revision + 1))
    const custom = requests.at(-1)!
    expect(custom.document.metadata.web_pattern_preset).toBeUndefined()
    expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(requests.at(-1)?.document.metadata.web_pattern_preset).toEqual(recipe.document.metadata.web_pattern_preset))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(requests.at(-1)?.document_revision).toBe(custom.document_revision + 2))
    expect(requests.at(-1)?.document).toEqual(custom.document)
    await waitFor(async () => expect((await drafts.loadDraft())?.dto.document).toEqual(custom.document))
    view.unmount(); render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(requests.at(-1)?.document_id).toBe(original.document_id))
    expect(requests.at(-1)?.document).toEqual(original.document)
    expect(screen.getByLabelText('编辑状态')).toHaveTextContent('Editing · 待提交')
    expect(screen.queryByRole('button', { name: '← 返回之前作品' })).not.toBeInTheDocument()
    await waitFor(async () => expect((await drafts.loadDraft())?.dto).toEqual(original))
    expect((await drafts.loadDraft())?.pending_layout).toEqual(pending)
    expect((await drafts.loadDraft())?.design_display).toEqual(display)
    expect((await drafts.loadBeforeExampleDraft())?.dto.document).toEqual(custom.document)
  }, 10000) // Full create/custom/history/refresh/return flow now renders six cards.

  it('failed return keeps both works and the button usable; one retry restores without losing the edited recipe', async () => {
    const original = createExampleDocument('basic-grid', 'return-failure')
    delete original.document.metadata['xiaomang_pattern_lab.example_id']
    await drafts.saveDraft(original, 'original.svg', null)
    const requests = backend(); render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await waitFor(() => expect(requests.at(-1)?.document_id).toBe(original.document_id))
    fireEvent.click(screen.getByRole('button', { name: `图案预设 · ${patternPresets.length}套` }))
    fireEvent.click(screen.getByRole('button', { name: '创建斜向潮汐' }))
    await waitFor(() => expect(within(screen.getByLabelText('待应用效果操作')).getByRole('button', { name: '应用效果' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    const recipe = requests.at(-1)!, count = requests.length
    const save = vi.spyOn(drafts, 'saveExampleReturn').mockRejectedValueOnce(new Error('quota fixture'))
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await screen.findByText('quota fixture')
    expect(requests).toHaveLength(count)
    expect((await drafts.loadDraft())?.dto.document_id).toBe(recipe.document_id)
    expect((await drafts.loadBeforeExampleDraft())?.dto).toEqual(original)
    expect(screen.getByRole('button', { name: '← 返回之前作品' })).toBeEnabled()
    save.mockRestore()
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(requests.at(-1)?.document_id).toBe(original.document_id))
    expect((await drafts.loadBeforeExampleDraft())?.dto.document_id).toBe(recipe.document_id)
  })

  it.each(['absent', 'same-document'])('does not show an invalid return target: %s', async kind => {
    const original = createExampleDocument('basic-grid', 'invalid-return')
    delete original.document.metadata['xiaomang_pattern_lab.example_id']
    if (kind === 'same-document') await drafts.saveBeforeExampleDraft(original, 'same.svg', null)
    await drafts.saveDraft(original, 'original.svg', null, { pending_layout: null, example_session_active: true })
    backend(); render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '恢复上次编辑' }))
    await screen.findByLabelText('最终二维几何，单位毫米')
    expect(screen.queryByRole('button', { name: '← 返回之前作品' })).not.toBeInTheDocument()
  })
})
