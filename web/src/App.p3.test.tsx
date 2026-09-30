import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

vi.mock('./manufacturing/ThreePreview', () => ({
  ThreePreview: ({ resultId }: { resultId: string }) => <div aria-label="三维模型预览">GLB {resultId}</div>,
}))

const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300,
  status, json: async () => value } as Response)
const source = { schema_version: 1, canvas: { width: 70, height: 30, unit: 'mm', mm_per_unit: 1 },
  reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
  elements: [{ id: 'circle-1', type: 'circle', x: 10, y: 10, width: 10, height: 10, rotation: 0, visible: true }] }

function mockApi(stlStatus = 200) {
  const calls: string[] = []
  const mock = vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    calls.push(path)
    if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    if (path.endsWith('/model.stl')) return Promise.resolve({ ok: stlStatus === 200, status: stlStatus,
      arrayBuffer: async () => new Uint8Array(100).buffer,
      json: async () => ({ message: '制造结果已过期' }) } as Response)
    const body = JSON.parse(String(init?.body)) as { document: PatternDocumentDTO; document_id: string; document_revision: number; height_mm: number }
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: body.document_id,
      document_revision: body.document_revision, recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
    if (path.endsWith('/evaluate')) return Promise.resolve(reply({ schema_version: '1.0', document_id: body.document_id,
      document_revision: body.document_revision, geometry: body.document.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 5, min_y: 5, max_x: 15, max_y: 15, width: 10, height: 10, units: 'mm' }, warnings: [] }))
    if (path.endsWith('/manufacturing/build')) return Promise.resolve(reply({ schema_version: '1.0', status: 'completed',
      manufacturing_result_id: 'mesh-1', document_id: body.document_id, document_revision: body.document_revision,
      geometry_validation_summary: { checked_count: 1, error_count: 0, warning_count: 0, issues: [] },
      connectivity_summary: { component_count: 1, isolated_count: 0 },
      conversion_summary: { input_count: 1, converted_count: 1, skipped_count: 0, warnings: [] },
      mesh_validation_summary: { is_watertight: true, component_count: 1, error_count: 0, warning_count: 0, issues: [] },
      component_count: 1, bounds_mm: { size_x: 10, size_y: 10, size_z: body.height_mm, units: 'mm' }, warnings: [] }))
    return Promise.resolve(reply({ message: 'unexpected route' }, 404))
  })
  vi.stubGlobal('fetch', mock)
  return { mock, calls }
}

async function openAndBuild() {
  render(<App />)
  await screen.findByText('Backend Online')
  const raw = JSON.stringify(source)
  const file = new File([raw], 'test.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => raw })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
  fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
  fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
  await screen.findByText('模型已生成')
  fireEvent.click(screen.getByRole('button', { name: /三维预览 3D Preview/ }))
}

describe('P3 preview and STL remain tied to the current build', () => {
  it('offers visible preview and STL export below the manufacturing summary', async () => {
    const api = mockApi()
    const createUrl = vi.fn(() => 'blob:stl')
    vi.stubGlobal('URL', { ...URL, createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await openAndBuild()
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    const report = screen.getByText('Mesh 状态').closest('.manufacturing-report')
    expect(report).not.toBeNull()
    expect(screen.getByRole('button', { name: '3D 预览' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '导出 STL' }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(api.calls.filter((url) => url.endsWith('/mesh-1/model.stl'))).toHaveLength(1)
    click.mockRestore()
  })

  it('enables preview/download after build without touching revision, then disables both when stale', async () => {
    const api = mockApi()
    const createUrl = vi.fn(() => 'blob:stl')
    vi.stubGlobal('URL', { ...URL, createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await openAndBuild()
    expect(screen.getByLabelText('三维模型预览')).toHaveTextContent('mesh-1')
    expect(screen.getByText(/10.00 × 10.00 × 2.00 mm/)).toBeInTheDocument()
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '导出 STL' }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(createUrl).toHaveBeenCalledOnce()
    expect(api.calls.filter((url) => url.endsWith('/mesh-1/model.stl'))).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.change(screen.getByLabelText('厚度 mm'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: /三维预览 3D Preview/ }))
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    expect(screen.queryByLabelText('三维模型预览')).toBeNull()
    expect(screen.getByText(/旧预览与 STL 已失效/)).toBeInTheDocument()
    click.mockRestore()
  })

  it('shows download failure inline without clearing the design', async () => {
    mockApi(404)
    await openAndBuild()
    fireEvent.click(screen.getByRole('button', { name: '导出 STL' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('制造结果已过期')
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    expect(await screen.findByRole('img', { name: '最终二维几何，单位毫米' })).toBeInTheDocument()
  })

  it('invalidates preview and STL after a design revision', async () => {
    const api = mockApi()
    await openAndBuild()
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="circle-1"]')!, { button: 0, clientX: 20, clientY: 20, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 25, clientY: 25, pointerId: 1 })
    fireEvent.pointerUp(canvas, { clientX: 30, clientY: 30, pointerId: 1 })
    await screen.findByText('revision 1')
    fireEvent.click(screen.getByRole('button', { name: /三维预览 3D Preview/ }))
    expect(screen.queryByLabelText('三维模型预览')).toBeNull()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    expect(api.calls.filter((url) => url.endsWith('/mesh-1/model.stl'))).toHaveLength(0)
  })
})
