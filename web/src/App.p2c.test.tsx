import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { loadDraft } from './draft/localDraft'
import type { PatternDocumentDTO } from './model/types'
import basicGrid from './examples/fixtures/basic-grid.pattern.json'
import gradientGrid from './examples/fixtures/gradient-grid.pattern.json'

const param = (id: string, label: string, value: number) => ({ id, label, type: 'number',
  default: value, value, min: -180, max: 180, step: 1, unit: '', options: [] })
const catalog = { schema_version: '1.0', units: 'mm', definitions: { layout: { grid: { label: '规则矩阵',
  parameters: [{ ...param('rows', '行数', 3), type: 'integer', min: 1, max: 100 },
    { ...param('columns', '列数', 3), type: 'integer', min: 1, max: 100 }] } },
  field: { linear: { label: '线性场', parameters: [param('angle', '角度', 0)] } },
  modifier: { size: { label: '尺寸', parameters: [param('max_output', '最大尺寸', 1)] },
    rotation: { label: '旋转', parameters: [param('max_output', '最大角度', 45)] } } } }
const reply = (value: unknown): Response => ({ ok: true, status: 200, json: async () => value }) as Response

function mockBackend() {
  const evaluated: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm',
      parameter_definitions: catalog }))
    const dto = (JSON.parse(String(init?.body)) as { document: PatternDocumentDTO }).document
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: dto.document_id,
      document_revision: dto.document_revision, recommended_family: 'grid', confidence: .95,
      analysis_status: 'matched' }))
    evaluated.push(dto)
    return Promise.resolve(reply({ schema_version: '1.0', document_id: dto.document_id,
      document_revision: dto.document_revision,
      geometry: dto.document.elements.map((item) => ({ ...item, units: 'mm' })),
      bounds_mm: { min_x: 10, min_y: 10, max_x: 50, max_y: 50, width: 40, height: 40, units: 'mm' },
      warnings: [] }))
  }))
  return evaluated
}

function openFixture(document: unknown, name: string) {
  const raw = JSON.stringify(document)
  const file = new File([raw], name, { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => raw })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
}
function gridRows(dto: PatternDocumentDTO): number {
  return (dto.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows
}

describe('P2-C refresh continuity', () => {
  it('restores an unapplied Grid value without changing the committed document or Undo history', async () => {
    const evaluated = mockBackend()
    const view = render(<App />)
    await screen.findByText('Backend Online')
    openFixture(basicGrid, 'my-grid.pattern.json')
    await screen.findByLabelText('最终二维几何，单位毫米')
    fireEvent.change(screen.getByLabelText('行数'), { target: { value: '4' } })
    fireEvent.blur(screen.getByLabelText('行数'))
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await screen.findByText('revision 1')
    await waitFor(async () => expect((await loadDraft())?.dto.document_revision).toBe(1))
    fireEvent.change(screen.getByLabelText('行数'), { target: { value: '5' } })
    fireEvent.blur(screen.getByLabelText('行数'))
    expect(screen.getByText('有未应用修改')).toBeInTheDocument()
    const unsavedLeave = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(unsavedLeave)
    expect(unsavedLeave.defaultPrevented).toBe(true)
    await waitFor(async () => expect((await loadDraft())?.pending_layout?.changed).toBe(true))
    await screen.findByText('已保存')
    const savedLeave = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(savedLeave)
    expect(savedLeave.defaultPrevented).toBe(false)
    expect(gridRows((await loadDraft())!.dto)).toBe(4)
    view.unmount()

    render(<App />)
    await screen.findByRole('region', { name: '恢复上次编辑' })
    fireEvent.click(screen.getByRole('button', { name: '恢复上次编辑' }))
    await screen.findByLabelText('最终二维几何，单位毫米')
    expect(screen.getByLabelText('行数')).toHaveValue(5)
    expect(screen.getByText('有未应用修改')).toBeInTheDocument()
    expect(screen.getByText(/已恢复上次编辑及未应用的布局参数/)).toBeInTheDocument()
    expect(screen.getByText(/刷新后撤销历史不会保留/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(gridRows(evaluated.at(-1)!)).toBe(4)
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await screen.findByText('revision 2')
    await waitFor(async () => expect((await loadDraft())?.pending_layout).toBeNull())
    expect(gridRows((await loadDraft())!.dto)).toBe(5)
    fireEvent.change(screen.getByLabelText('行数'), { target: { value: '6' } })
    fireEvent.blur(screen.getByLabelText('行数'))
    fireEvent.click(screen.getByRole('button', { name: '取消布局' }))
    expect(screen.getByLabelText('行数')).toHaveValue(5)
    expect(screen.queryByText('有未应用修改')).not.toBeInTheDocument()
    await waitFor(async () => expect((await loadDraft())?.pending_layout).toBeNull())
  })

  it('restores committed Field and Modifier edits but starts a new Undo session', async () => {
    mockBackend()
    const view = render(<App />)
    await screen.findByText('Backend Online')
    openFixture(gradientGrid, 'my-gradient.pattern.json')
    await screen.findByLabelText('最终二维几何，单位毫米')
    const angle = screen.getByRole('spinbutton', { name: /^角度/ })
    fireEvent.change(angle, { target: { value: '25' } })
    fireEvent.blur(angle)
    await screen.findByText('revision 1')
    const size = screen.getByRole('spinbutton', { name: /^最大尺寸/ })
    fireEvent.change(size, { target: { value: '2' } })
    fireEvent.blur(size)
    await screen.findByText('revision 2')
    await waitFor(async () => expect((await loadDraft())?.dto.document_revision).toBe(2))
    view.unmount()
    render(<App />)
    await screen.findByRole('region', { name: '恢复上次编辑' })
    fireEvent.click(screen.getByRole('button', { name: '恢复上次编辑' }))
    await screen.findByLabelText('最终二维几何，单位毫米')
    expect(screen.getByRole('spinbutton', { name: /^角度/ })).toHaveValue(25)
    expect(screen.getByRole('spinbutton', { name: /^最大尺寸/ })).toHaveValue(2)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(screen.getByText(/刷新后撤销历史不会保留/)).toBeInTheDocument()
  })

  it('restores the example-session return link after refresh without replacing the original work', async () => {
    mockBackend()
    const view = render(<App />)
    await screen.findByText('Backend Online')
    const original = structuredClone(basicGrid)
    delete (original.metadata as Record<string, unknown>)['xiaomang_pattern_lab.example_id']
    openFixture(original, 'my-original.pattern.json')
    await screen.findByLabelText('最终二维几何，单位毫米')
    await waitFor(async () => expect((await loadDraft())?.dto.document_id).toBeTruthy())
    const originalId = (await loadDraft())!.dto.document_id
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await screen.findByText('正在试用示例：基础圆点阵列')
    await waitFor(async () => expect((await loadDraft())?.example_session_active).toBe(true))
    expect(screen.getByText('已保存')).toBeInTheDocument()
    view.unmount()
    render(<App />)
    await screen.findByRole('region', { name: '恢复上次编辑' })
    fireEvent.click(screen.getByRole('button', { name: '恢复上次编辑' }))
    await screen.findByText('正在试用示例：基础圆点阵列')
    fireEvent.click(await screen.findByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(screen.getByLabelText('当前项目')).toHaveTextContent('my-original.pattern.json'))
    await waitFor(async () => expect((await loadDraft())?.dto.document_id).toBe(originalId))
  })
})
