import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

const catalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: { free: { label: '自由布局', parameters: [] } },
  field: { wave: { label: '波浪场', parameters: [
    { id: 'wavelength', label: '波长', type: 'number', default: 40, value: 40,
      min: 1, max: 100, step: 1, unit: 'mm', options: [] },
  ] }, linear: { label: '线性场', parameters: ['start', 'end'].map((id) => ({
    id, label: id === 'start' ? '起点' : '终点', type: 'number', default: id === 'start' ? 0 : 100,
    value: 0, min: -1000, max: 1000, step: 1, unit: 'mm', options: [],
  })) } }, modifier: {},
} }
function fixture() {
  return { schema_version: 1, canvas: { width: 100, height: 100, unit: 'mm', mm_per_unit: 1 },
    reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {},
    elements: [{ id: 'a', type: 'circle', x: 10, y: 10, width: 4, height: 4, rotation: 0, visible: true }],
    fields: [{ id: 'wave-1', type: 'wave', parameters: { wavelength: 40 } }], modifiers: [],
  }
}
function backend() {
  const requests: PatternDocumentDTO[] = []
  const pending: Array<{ dto: PatternDocumentDTO; resolve: (response: Response) => void }> = []
  const reply = (value: unknown, status = 200) => ({ ok: status === 200, status, json: async () => value }) as Response
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    if (String(url).endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (String(url).endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog }))
    const dto = (JSON.parse(String(init?.body)) as { document: PatternDocumentDTO }).document
    if (String(url).endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: dto.document_id,
      document_revision: dto.document_revision, recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
    requests.push(dto)
    return new Promise<Response>((resolve) => pending.push({ dto, resolve }))
  }))
  const flush = (options: { fail?: boolean; hide?: boolean } = {}) => {
    const { dto, resolve } = pending.shift()!
    resolve(options.fail ? reply({ message: '测试求值失败' }, 422) : reply({ schema_version: '1.0',
      document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: options.hide ? [] : dto.document.elements.map((item) => ({ ...item, units: 'mm' })),
      bounds_mm: options.hide ? null : { min_x: 8, min_y: 8, max_x: 12, max_y: 12, width: 4, height: 4, units: 'mm' }, warnings: [] }))
  }
  return { requests, pending, flush }
}
async function open(api: ReturnType<typeof backend>, doc: unknown = fixture()) {
  render(<App />)
  await screen.findByText('Backend Online')
  const json = JSON.stringify(doc)
  const file = new File([json], 'p1e.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => json })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await waitFor(() => expect(api.pending).toHaveLength(1))
  api.flush()
  await waitFor(() => expect(screen.getByLabelText('参数检查器')).toBeEnabled())
  return screen.getByRole('img', { name: '最终二维几何，单位毫米' })
}
async function ready(api: ReturnType<typeof backend>, options = {}) {
  await waitFor(() => expect(api.pending).toHaveLength(1))
  api.flush(options)
  await waitFor(() => expect(screen.getByLabelText('参数检查器')).toBeEnabled())
}
function changeWavelength(value: string) {
  const slider = screen.getByRole('slider', { name: '波长滑杆' })
  fireEvent.change(slider, { target: { value } })
  fireEvent.pointerUp(slider)
}

describe('P1-E continuous parameter editing', () => {
  it('restores controls after repeated client validation failures without a backend request', async () => {
    const api = backend()
    await open(api, { ...fixture(), fields: [{ id: 'linear-1', type: 'linear', parameters: { start: 0, end: 100 } }] })
    for (let attempt = 0; attempt < 2; attempt++) {
      fireEvent.change(screen.getByLabelText('起点 (mm)'), { target: { value: '100' } })
      fireEvent.blur(screen.getByLabelText('起点 (mm)'))
      await waitFor(() => expect(screen.getByLabelText('起点 (mm)')).toHaveValue(0))
      expect(api.requests).toHaveLength(1)
      expect(screen.getByRole('alert')).toHaveTextContent('线性场终点必须大于起点')
    }
    fireEvent.change(screen.getByLabelText('起点 (mm)'), { target: { value: '50' } })
    fireEvent.blur(screen.getByLabelText('起点 (mm)'))
    await ready(api)
    expect(screen.getByLabelText('起点 (mm)')).toHaveValue(50)
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('preserves sections and viewport, resets as one history step and handles shortcuts outside inputs', async () => {
    const api = backend()
    const canvas = await open(api)
    const layoutToggle = screen.getByRole('button', { name: /LAYOUT/ })
    fireEvent.click(layoutToggle)
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    const view = canvas.querySelector('g')!.getAttribute('transform')
    const inspector = screen.getByLabelText('右侧检查器')
    inspector.scrollTop = 150
    const slider = screen.getByRole('slider', { name: '波长滑杆' })
    fireEvent.change(slider, { target: { value: '50' } })
    fireEvent.change(slider, { target: { value: '60' } })
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(60)
    expect(screen.getByLabelText('编辑状态')).toHaveTextContent('Editing')
    expect(api.requests).toHaveLength(1)
    fireEvent.pointerUp(slider)
    fireEvent.blur(slider)
    expect(api.requests).toHaveLength(2)
    expect(screen.getByLabelText('编辑状态')).toHaveTextContent('Evaluating')
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1)
    await ready(api)
    expect(layoutToggle).toHaveAttribute('aria-expanded', 'false')
    expect(inspector.scrollTop).toBe(150)
    expect(canvas.querySelector('g')).toHaveAttribute('transform', view!)
    fireEvent.click(screen.getByRole('button', { name: '重置波长' }))
    expect(api.requests).toHaveLength(3)
    expect(api.requests.at(-1)!.document_revision).toBe(2)
    expect(api.requests.at(-1)!.document.fields[0].parameters).toEqual({ wavelength: 40 })
    await ready(api)
    fireEvent.keyDown(screen.getByLabelText('波长 (mm)'), { key: 'z', ctrlKey: true })
    expect(api.requests).toHaveLength(3)
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true })
    await ready(api)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(60)
    fireEvent.keyDown(window, { key: 'Z', ctrlKey: true, shiftKey: true })
    await ready(api)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(40)
    expect(layoutToggle).toHaveAttribute('aria-expanded', 'false')
    expect(canvas.querySelector('g')).toHaveAttribute('transform', view!)
  })

  it('allows retry, reset and Undo after failure, and clears only a disappeared selection', async () => {
    const api = backend()
    const canvas = await open(api)
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="a"]')!, { button: 0 })
    changeWavelength('60')
    await ready(api)
    const before = canvas.innerHTML
    changeWavelength('70')
    await ready(api, { fail: true })
    expect(screen.getByRole('alert')).toHaveTextContent('测试求值失败')
    expect(canvas.innerHTML).toBe(before)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(60)
    expect(canvas.querySelector('.selected')).toHaveAttribute('data-element-id', 'a')
    // Retrying the identical rejected value must not be suppressed by draft refs.
    changeWavelength('70')
    await ready(api, { fail: true })
    expect(api.requests).toHaveLength(4)
    fireEvent.click(screen.getByRole('button', { name: '重置波长' }))
    await ready(api, { fail: true })
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true })
    await ready(api)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(40)
    expect(screen.queryByRole('alert')).toBeNull()
    fireEvent.keyDown(window, { key: 'y', ctrlKey: true })
    await ready(api)
    expect(screen.getByLabelText('波长 (mm)')).toHaveValue(60)
    changeWavelength('80')
    await ready(api, { hide: true })
    expect(within(screen.getByRole('region', { name: '元素变换' })).getByText(/No selection/)).toBeVisible()
    changeWavelength('60')
    await ready(api)
    expect(canvas.querySelector('[data-element-id="a"]')).not.toBeNull()
    expect(canvas.querySelector('.selected')).toBeNull()
  })
})
