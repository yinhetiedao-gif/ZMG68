import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { linearCatalog } from './test/linearSizeFixture'
import type { PatternDocumentDTO } from './model/types'
import * as drafts from './draft/localDraft'

const source = { schema_version: 1, canvas: { width: 60, height: 40, unit: 'mm', mm_per_unit: 1 },
  reference: {}, elements: [{ id: 'dot', type: 'circle', x: 20, y: 15, width: 4, height: 4, rotation: 0, visible: true }],
  groups: [], transforms: {}, fields: [], modifiers: [], metadata: {} }
function backend() {
  const requests: PatternDocumentDTO[] = []; let failCandidate = false
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status })
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: linearCatalog })
    const body = JSON.parse(String(init?.body)), dto = body.document as PatternDocumentDTO
    if (String(url).endsWith('/evaluate')) {
      requests.push(dto)
      if (failCandidate && dto.document.modifiers.length) { failCandidate = false; return reply({ code: 'staging_busy', message: '服务忙碌，请等待后再操作。' }, 429) }
      return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
        geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })), warnings: [],
        bounds_mm: { min_x: 18, min_y: 13, max_x: 22, max_y: 17, width: 4, height: 4, units: 'mm' } })
    }
    return reply({ message: '本测试不执行三维制造' }, 503)
  }))
  return { requests, fail: () => { failCandidate = true } }
}
async function open() {
  await screen.findByText('Backend Online')
  const raw = JSON.stringify(source), file = new File([raw], 'r1.pattern.json')
  Object.defineProperty(file, 'text', { value: async () => raw })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  return await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
}
describe('Web R1 current workflow wiring', () => {
  it('retains the exact zoom and pan through a workspace round trip, without another Evaluate', async () => {
    const api = backend(); render(<App />); const canvas = await open()
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    fireEvent.pointerDown(canvas, { button: 1, clientX: 50, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 83, clientY: 67, pointerId: 1 })
    fireEvent.pointerUp(canvas, { clientX: 83, clientY: 67, pointerId: 1 })
    const transform = canvas.querySelector('g[transform]')!.getAttribute('transform'), count = api.requests.length
    fireEvent.click(screen.getByRole('button', { name: '制造 Manufacture' }))
    fireEvent.click(screen.getByRole('button', { name: '设计 Design' }))
    expect(screen.getByRole('img', { name: '最终二维几何，单位毫米' }).querySelector('g[transform]')!.getAttribute('transform')).toBe(transform)
    expect(api.requests).toHaveLength(count)
  })
  it('saved official design plus failed pending preview is accurate; same-input Retry and Cancel never commit', async () => {
    const api = backend(); render(<App />); await open(); await screen.findByText('已保存')
    const before = (await drafts.loadDraft())!.dto
    api.fail(); fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    const retry = await screen.findByRole('button', { name: '重试尺寸预览' })
    expect(screen.getByText('正式作品已保存 · 有未应用预览')).toBeInTheDocument()
    const actions = within(screen.getByLabelText('待应用效果操作'))
    expect(actions.getByRole('button', { name: '应用效果' })).toBeDisabled()
    const failed = api.requests.at(-1), count = api.requests.length
    fireEvent.click(retry)
    await waitFor(() => expect(actions.getByRole('button', { name: '应用效果' })).toBeEnabled())
    expect(api.requests).toHaveLength(count + 1); expect(api.requests.at(-1)).toEqual(failed)
    expect((await drafts.loadDraft())!.dto).toEqual(before)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(actions.getByRole('button', { name: '取消效果' }))
    expect(screen.getByText('已保存')).toBeInTheDocument()
    expect((await drafts.loadDraft())!.dto).toEqual(before)
  })
  it('failed official storage is not described as saved', async () => {
    backend(); vi.spyOn(drafts, 'saveDraft').mockRejectedValueOnce(new Error('storage blocked'))
    render(<App />); await open()
    expect(await screen.findByText('保存失败')).toBeInTheDocument()
    expect(screen.queryByText('已保存')).not.toBeInTheDocument()
    vi.restoreAllMocks()
  })
})
