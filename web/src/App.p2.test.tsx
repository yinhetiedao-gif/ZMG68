import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value }) as Response
const source = { schema_version: 1, canvas: { width: 70, height: 30, unit: 'mm', mm_per_unit: 1 },
  reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
  elements: [{ id: 'circle-1', type: 'circle', x: 10, y: 10, width: 10, height: 10, rotation: 0, visible: true }] }

function mockApi() {
  const builds: Array<{ body: Record<string, unknown>; resolve: (response: Response) => void }> = []
  const mock = vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    const body = JSON.parse(String(init?.body)) as { document: PatternDocumentDTO; document_id: string; document_revision: number }
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: body.document_id,
      document_revision: body.document_revision, recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
    if (path.endsWith('/evaluate')) return Promise.resolve(reply({ schema_version: '1.0', document_id: body.document_id,
      document_revision: body.document_revision, geometry: body.document.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 5, min_y: 5, max_x: 15, max_y: 15, width: 10, height: 10, units: 'mm' }, warnings: [] }))
    if (path.endsWith('/manufacturing/build')) return new Promise<Response>((resolve) => builds.push({ body: body as unknown as Record<string, unknown>, resolve }))
    return Promise.resolve(reply({ message: 'unexpected route' }, 404))
  })
  vi.stubGlobal('fetch', mock)
  const finish = (index: number, options: { status?: number; componentCount?: number; message?: string; failureId?: string } = {}) => {
    const { body, resolve } = builds[index]
    if (options.status) { resolve(reply({ message: options.message ?? '二维轮廓未闭合',
      details: options.failureId ? { failure_id: options.failureId } : null }, options.status)); return }
    resolve(reply({ schema_version: '1.0', status: 'completed', manufacturing_result_id: `mesh-${index}`,
      document_id: body.document_id, document_revision: body.document_revision,
      geometry_validation_summary: { checked_count: 1, error_count: 0, warning_count: 0, issues: [] },
      connectivity_summary: { component_count: options.componentCount ?? 1, isolated_count: 0 },
      conversion_summary: { input_count: 1, converted_count: 1, skipped_count: 0, warnings: [] },
      mesh_validation_summary: { is_watertight: true, component_count: options.componentCount ?? 1,
        error_count: 0, warning_count: 0, issues: [] },
      component_count: options.componentCount ?? 1,
      bounds_mm: { size_x: 57.2169, size_y: 19.8992, size_z: body.height_mm, units: 'mm' }, warnings: [] }))
  }
  return { mock, builds, finish }
}

async function openProject(api: ReturnType<typeof mockApi>) {
  render(<App />)
  await screen.findByText('Backend Online')
  const raw = JSON.stringify(source)
  const file = new File([raw], 'test.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => raw })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
  await waitFor(() => expect(api.mock.mock.calls.filter(([url]) => String(url).endsWith('/evaluate'))).toHaveLength(1))
  fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
  await screen.findByRole('heading', { name: '制造检查' })
}

describe('P2 web manufacturing derived workflow', () => {
  it('builds current revision once, reports warnings and never changes the design document', async () => {
    const api = mockApi()
    await openProject(api)
    expect(screen.getByText('尚未生成')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    await waitFor(() => expect(api.builds).toHaveLength(1))
    expect(screen.getByText('正在检查并生成…')).toBeInTheDocument()
    expect(api.builds[0].body).toMatchObject({ height_mm: 2, document_revision: 0 })
    api.finish(0, { componentCount: 3 })
    expect(await screen.findByText('模型已生成，存在提醒')).toBeInTheDocument()
    expect(screen.getByText('57.217 × 19.899 × 2 mm')).toBeInTheDocument()
    expect(screen.getByText('结果编号：mesh-0')).toBeInTheDocument()
    expect(screen.getByText('封闭 · Watertight · 0 个错误')).toBeInTheDocument()
    expect(screen.getByText(/3 个独立组件；请确认/)).toBeInTheDocument()
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(api.mock.mock.calls.filter(([url]) => String(url).endsWith('/evaluate'))).toHaveLength(1)
  })

  it('rejects invalid thickness; changing thickness marks old result stale and requires a new build', async () => {
    const api = mockApi()
    await openProject(api)
    fireEvent.change(screen.getByLabelText('厚度 mm'), { target: { value: '0' } })
    expect(screen.getByRole('button', { name: '检查并生成' })).toBeDisabled()
    expect(screen.getByText('厚度必须大于 0 mm。')).toBeInTheDocument()
    expect(api.builds).toHaveLength(0)
    fireEvent.change(screen.getByLabelText('厚度 mm'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(screen.getByText(/处理流程：二维几何检查.*已用/)).toBeInTheDocument()
    api.finish(0)
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('厚度 mm'), { target: { value: '3' } })
    expect(screen.getByText('结果已过期，请重新检查并生成')).toBeInTheDocument()
    expect(screen.queryByText('57.217 × 19.899 × 2 mm')).toBeNull()
    expect(screen.queryByText('结果编号：mesh-0')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    api.finish(1)
    expect(await screen.findByText('57.217 × 19.899 × 3 mm')).toBeInTheDocument()
  })

  it('shows validation failures without deleting the evaluated design or modifying revision', async () => {
    const api = mockApi()
    await openProject(api)
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    api.finish(0, { status: 422, message: '二维轮廓未闭合' })
    expect(await screen.findByText('生成失败')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('二维轮廓未闭合')
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    expect(canvas.querySelector('[data-element-id="circle-1"]')).not.toBeNull()
  })

  it('shows the server failure ID only when a dev snapshot was saved', async () => {
    const api = mockApi()
    await openProject(api)
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    api.finish(0, { status: 422, message: 'Mesh 存在退化三角面', failureId: 'test-failure-001' })
    expect(await screen.findByRole('alert')).toHaveTextContent('failure_id: test-failure-001')
    expect(screen.getByText('revision 0')).toBeInTheDocument()
  })

  it('marks a built result stale after a design commit and never treats the old result as current', async () => {
    const api = mockApi()
    await openProject(api)
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    api.finish(0)
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="circle-1"]')!, { button: 0, clientX: 20, clientY: 20, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 25, clientY: 25, pointerId: 1 })
    fireEvent.pointerUp(canvas, { clientX: 30, clientY: 30, pointerId: 1 })
    await screen.findByText('revision 1')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    expect(screen.getByText('结果已过期，请重新检查并生成')).toBeInTheDocument()
    expect(screen.queryByText('57.217 × 19.899 × 2 mm')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(api.builds).toHaveLength(2)
    expect(api.builds[1].body.document_revision).toBe(1)
  })

  it('ignores a late manufacturing response after the thickness changes', async () => {
    const api = mockApi()
    await openProject(api)
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(api.builds).toHaveLength(1)
    fireEvent.change(screen.getByLabelText('厚度 mm'), { target: { value: '3' } })
    expect(screen.getByText('结果已过期，请重新检查并生成')).toBeInTheDocument()
    api.finish(0)
    await waitFor(() => expect(screen.queryByText('结果编号：mesh-0')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    api.finish(1)
    expect(await screen.findByText('结果编号：mesh-1')).toBeInTheDocument()
  })
})
