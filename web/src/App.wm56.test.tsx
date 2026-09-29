import { readFileSync } from 'node:fs'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

type Dot = { id: string; type: string; x: number; y: number; width: number; height: number;
  rotation: number; visible: boolean; style: { fill: string } }
type Doc = { schema_version: number; canvas: { width: number; height: number; unit: string; mm_per_unit: number };
  reference: Record<string, unknown>; elements: Dot[]; groups: unknown[]; transforms: Record<string, unknown>;
  metadata: Record<string, unknown>; fields: unknown[]; modifiers: unknown[] }
type Payload = { document_id: string; document_revision: number; document: { document: Doc } }

function reply(data: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => data } as Response
}

function fixture(count = 144): Doc {
  return { schema_version: 1, canvas: { width: 120, height: 120, unit: 'mm', mm_per_unit: 1 },
    reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
    elements: Array.from({ length: count }, (_, i) => ({ id: `dot-${i}`, type: 'circle',
      x: 10 + i % 12 * 8, y: 10 + Math.floor(i / 12) * 8, width: 4, height: 4,
      rotation: 0, visible: true, style: { fill: '#000' } })),
  }
}

function upload(doc: Doc) {
  const contents = JSON.stringify(doc)
  const file = new File([contents], 'matrix.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => contents })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
}

function backend(fail = false) {
  const pending: { payload: Payload; resolve: (response: Response) => void }[] = []
  const mock = vi.fn<typeof fetch>((url, init) => {
    if (String(url).endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (String(url).endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    if (String(url).endsWith('/analyze-pattern')) {
      const dto = JSON.parse(String(init?.body)) as { document: { document_id: string; document_revision: number } }
      return Promise.resolve(reply({ document_id: dto.document.document_id,
        document_revision: dto.document.document_revision, recommended: 'free', families: [], warnings: [] }))
    }
    const payload = JSON.parse(String(init?.body)) as Payload
    return new Promise<Response>((resolve) => pending.push({ payload, resolve }))
  })
  vi.stubGlobal('fetch', mock)
  const flush = () => {
    const request = pending.shift()!
    const { payload } = request
    request.resolve(fail && payload.document_revision > 0 ? reply({ message: '模拟求值错误' }, 422)
      : reply({ schema_version: '1.0', document_id: payload.document_id,
        document_revision: payload.document_revision,
        geometry: payload.document.document.elements.map((element) => ({ ...element, units: 'mm' })),
        bounds_mm: { min_x: 8, min_y: 8, max_x: 104, max_y: 104, width: 96, height: 96, units: 'mm' }, warnings: [] }))
    return payload
  }
  return { pending, flush }
}

async function opened(doc: Doc, api: ReturnType<typeof backend>) {
  render(<App />)
  await screen.findByText('Backend Online')
  upload(doc)
  await waitFor(() => expect(api.pending).toHaveLength(1))
  const before = api.flush()
  const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
  await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(doc.elements.length))
  return { canvas, before }
}

describe('WM5.6 edit visibility and commit boundary', () => {
  it('keeps the 144-element frame during direct drag and commits once on pointerup', async () => {
    const api = backend()
    const { canvas } = await opened(fixture(), api)
    const node = canvas.querySelector('[data-element-id="dot-0"]')!
    fireEvent.pointerDown(node, { button: 0, clientX: 10, clientY: 10, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 12, clientY: 10, pointerId: 1 })
    fireEvent.pointerMove(canvas, { clientX: 14, clientY: 10, pointerId: 1 })
    expect(api.pending).toHaveLength(0)
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144)
    fireEvent.pointerUp(canvas, { clientX: 14, clientY: 10, pointerId: 1 })
    await waitFor(() => expect(api.pending).toHaveLength(1))
    expect(api.pending[0].payload.document_revision).toBe(1)
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144)
    api.flush()
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144))
    expect(screen.getByText('revision 1')).toBeInTheDocument()
  })

  it.each([
    ['位置 X mm', '24', 'x'], ['宽度 mm', '8', 'width'],
    ['高度 mm', '7', 'height'], ['旋转 °', '45', 'rotation'],
  ])('%s keeps 144 elements while editing, loading and after Evaluate', async (label, value, key) => {
    const api = backend()
    const doc = fixture()
    const { canvas } = await opened(doc, api)
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="dot-0"]')!, { button: 0 })
    const input = screen.getByRole('spinbutton', { name: label })
    fireEvent.change(input, { target: { value: '' } })
    expect(api.pending).toHaveLength(0)
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144)
    fireEvent.change(input, { target: { value } })
    expect(api.pending).toHaveLength(0)
    fireEvent.blur(input)
    await waitFor(() => expect(api.pending).toHaveLength(1))
    expect(api.pending[0].payload.document_revision).toBe(1)
    expect(api.pending[0].payload.document.document.elements[0][key as keyof Dot]).toBe(Number(value))
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144)
    expect(canvas.querySelector('[data-element-id="dot-0"] circle')).toHaveAttribute('cx', '10')
    api.flush()
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144))
    expect(canvas.querySelector('[data-element-id="dot-0"]')).not.toBeNull()
  })

  it('retains all imported dot geometry after a failed edit and rolls back revision', async () => {
    const api = backend(true)
    const raw = JSON.parse(readFileSync('../work/foundation0/test_dot_grid/document.pattern.json', 'utf8')) as Doc
    raw.canvas.mm_per_unit = 1
    const { canvas } = await opened(raw, api)
    const first = raw.elements[0]
    fireEvent.pointerDown(canvas.querySelector(`[data-element-id="${first.id}"]`)!, { button: 0 })
    const input = screen.getByRole('spinbutton', { name: '宽度 mm' })
    fireEvent.change(input, { target: { value: '0' } })
    fireEvent.blur(input)
    expect(api.pending).toHaveLength(0)
    fireEvent.change(screen.getByRole('spinbutton', { name: '宽度 mm' }), { target: { value: '8' } })
    fireEvent.blur(screen.getByRole('spinbutton', { name: '宽度 mm' }))
    await waitFor(() => expect(api.pending).toHaveLength(1))
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(raw.elements.length)
    api.flush()
    expect(await screen.findByRole('alert')).toHaveTextContent('模拟求值错误')
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(raw.elements.length)
    expect(screen.getByText('revision 0')).toBeInTheDocument()
  })
})
