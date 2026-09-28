import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function reply(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => value } as Response
}

function pattern(count = 1, unit = 'mm') {
  const elements = Array.from({ length: count }, (_, index) => ({
    id: `dot-${index}`, type: 'circle', x: 10 + (index % 12) * 8,
    y: 10 + Math.floor(index / 12) * 8,
    width: 4, height: 4, rotation: 0, visible: true, style: { fill: '#000' },
  }))
  return {
    schema_version: 1,
    canvas: { width: 120, height: 120, unit, mm_per_unit: unit === 'mm' ? 1 : null },
    reference: { source_path: '', visible: false, preprocessing: {}, metadata: {} },
    elements, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
  }
}

function mockBackend(count = 1) {
  const mock = vi.fn<typeof fetch>((url, init) => {
    if (String(url).endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (String(url).endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    const payload = JSON.parse(String(init?.body)) as { document_id: string; document_revision: number; document: { document: ReturnType<typeof pattern> } }
    const geometry = payload.document.document.elements.map((item) => ({ ...item, units: 'mm' }))
    return Promise.resolve(reply({
      schema_version: '1.0', document_id: payload.document_id,
      document_revision: payload.document_revision, geometry,
      bounds_mm: { min_x: 8, min_y: 8, max_x: 106, max_y: count > 1 ? 102 : 12,
        width: 98, height: count > 1 ? 94 : 4, units: 'mm' },
      warnings: [],
    }))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

function uploadJson(value: unknown, name = 'project.pattern.json') {
  const file = new File([JSON.stringify(value)], name, { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(value) })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
}

describe('WM5 project → Python Evaluate → 2D workspace', () => {
  it('opens a local project, renders evaluated geometry and selects by stable ID', async () => {
    const fetchMock = mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson(pattern())
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="dot-0"]')!, { button: 0, clientX: 200, clientY: 200 })
    expect(screen.getByText('已选元素')).toBeInTheDocument()
    expect(screen.getByText('dot-0')).toBeInTheDocument()
    expect(screen.getByText('10.00, 10.00 mm')).toBeInTheDocument()
  })

  it('shows invalid project errors without replacing the workspace', async () => {
    mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson({ nonsense: true })
    expect(await screen.findByRole('alert')).toHaveTextContent('不是 PatternDocument')
    expect(screen.getByText('打开项目查看二维图案')).toBeInTheDocument()
  })

  it('requests explicit mm mapping for a legacy 144-element project', async () => {
    const fetchMock = mockBackend(144)
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson(pattern(144, 'svg_user_unit'), '144-dots.pattern.json')
    expect(await screen.findByRole('dialog', { name: '设置毫米映射' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(0)
    fireEvent.change(screen.getByLabelText('1 SVG 单位对应多少 mm'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: '按此比例打开' }))
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144))
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
  })

  it('keeps pan, zoom and selection out of document requests', async () => {
    const fetchMock = mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson(pattern())
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    fireEvent.click(screen.getByRole('button', { name: '缩小' }))
    fireEvent.click(screen.getByRole('button', { name: '适合窗口' }))
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="dot-0"]')!, { button: 0 })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
  })

  it('commits one source drag only at pointerup and evaluates once', async () => {
    const fetchMock = mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson(pattern())
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
    const dot = canvas.querySelector('[data-element-id="dot-0"]')!
    fireEvent.pointerDown(dot, { button: 0, clientX: 20, clientY: 20, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 21, clientY: 21, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 22, clientY: 22, pointerId: 1 })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
    fireEvent.pointerUp(canvas, { clientX: 23, clientY: 23, pointerId: 1 })
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(2))
    const payload = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body)) as { document_revision: number }
    expect(payload.document_revision).toBe(1)
  })

  it('cancels an interrupted drag without changing the project or evaluating again', async () => {
    const fetchMock = mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson(pattern())
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
    const dot = canvas.querySelector('[data-element-id="dot-0"]')!
    fireEvent.pointerDown(dot, { button: 0, clientX: 20, clientY: 20, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 40, clientY: 40, pointerId: 1 })
    fireEvent.pointerCancel(canvas, { pointerId: 1 })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
    expect(screen.getByText('10.00, 10.00 mm')).toBeInTheDocument()
  })

  it('does not drag a parameterized result merely because its ID looks like a source ID', async () => {
    const fetchMock = mockBackend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadJson({ ...pattern(), metadata: { 'xiaomang_pattern_lab.parametric': { mode: 'grid' } } })
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
    fireEvent.pointerDown(canvas.querySelector('[data-element-id]')!, { button: 0, clientX: 20, clientY: 20 })
    expect(screen.getByText(/本阶段只读/)).toBeInTheDocument()
    fireEvent.pointerUp(canvas, { clientX: 30, clientY: 30 })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))).toHaveLength(1)
  })
})
