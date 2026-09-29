import { readFileSync } from 'node:fs'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function response(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => value } as Response
}

function documentFixture() {
  return {
    schema_version: 1,
    canvas: { width: 120, height: 120, unit: 'mm', mm_per_unit: 1 },
    reference: { source_path: '', visible: false, preprocessing: {}, metadata: {} },
    elements: [{ id: 'dot-0', type: 'circle', x: 10, y: 10, width: 4, height: 4,
      rotation: 0, visible: true, style: { fill: '#000' } }],
    groups: [], transforms: {},
    fields: [{ id: 'wave-1', type: 'wave', parameters: {
      angle: 0, wavelength: 40, phase: 0, amplitude: .5, offset: .5,
    } }],
    modifiers: [{ id: 'size-1', type: 'size', field_id: 'wave-1', enabled: true,
      mapping: { min_output: .5, max_output: 1.5, strength: 1, falloff: 1 } }],
    metadata: {},
  }
}

type Fixture = ReturnType<typeof documentFixture>

function backend(failRevision?: number) {
  const mock = vi.fn<typeof fetch>((url, init) => {
    if (String(url).endsWith('/health')) return Promise.resolve(response({ status: 'ok', contract_version: '1.0' }))
    if (String(url).endsWith('/contract')) return Promise.resolve(response({ schema_version: '1.0', units: 'mm' }))
    const payload = JSON.parse(String(init?.body)) as {
      document_id: string; document_revision: number; document: { document: Fixture }
    }
    if (payload.document_revision === failRevision) return Promise.resolve(response({ detail: 'WM6 simulated failure' }, 422))
    return Promise.resolve(response({ schema_version: '1.0', document_id: payload.document_id,
      document_revision: payload.document_revision,
      geometry: payload.document.document.elements.map((element) => ({ ...element, units: 'mm',
        ...((element.type === 'path' || element.type === 'filled_region')
          ? { path_data_coordinate_system: 'element_local' } : {}),
      })),
      bounds_mm: { min_x: 8, min_y: 8, max_x: 12, max_y: 12, width: 4, height: 4, units: 'mm' },
      warnings: [],
    }))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

function evaluations(mock: ReturnType<typeof backend>) {
  return mock.mock.calls.filter(([url]) => String(url).includes('/evaluate'))
}

function lastDocument(mock: ReturnType<typeof backend>): Fixture {
  const body = String(evaluations(mock).at(-1)?.[1]?.body)
  return (JSON.parse(body) as { document: { document: Fixture } }).document.document
}

function upload(value: Fixture) {
  const json = JSON.stringify(value)
  const file = new File([json], 'wm6.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => json })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
}

function uploadFixture(path: string) {
  const json = readFileSync(new URL(path, import.meta.url), 'utf8')
  const file = new File([json], 'actual.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => json })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
}

async function open(value = documentFixture()) {
  render(<App />)
  await screen.findByText('Backend Online')
  upload(value)
  const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
  await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1))
  return canvas
}

describe('WM6 Inspector and committed-document boundary', () => {
  it('keeps slider movements transient, then commits one Field revision and one Undo', async () => {
    const mock = backend()
    await open()
    const slider = screen.getByRole('slider', { name: '波长滑杆' })
    fireEvent.change(slider, { target: { value: '60' } })
    fireEvent.change(slider, { target: { value: '65' } })
    expect(evaluations(mock)).toHaveLength(1)
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(2))
    expect(lastDocument(mock).fields[0].parameters.wavelength).toBe(65)
    expect(screen.getByText('revision 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '撤销' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluations(mock)).toHaveLength(3))
    expect(lastDocument(mock).fields[0].parameters.wavelength).toBe(40)
    expect(screen.getByText('revision 2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(evaluations(mock)).toHaveLength(4))
    expect(lastDocument(mock).fields[0].parameters.wavelength).toBe(65)
    expect(screen.getByText('revision 3')).toBeInTheDocument()
  })

  it('commits direct source Transform where source mapping is unambiguous', async () => {
    const mock = backend()
    const plain = documentFixture()
    plain.fields = []
    plain.modifiers = []
    const canvas = await open(plain)
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="dot-0"]')!, { button: 0 })
    const xInput = screen.getByRole('spinbutton', { name: '位置 X mm' })
    fireEvent.change(xInput, { target: { value: '24' } })
    fireEvent.blur(xInput)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(2))
    expect(lastDocument(mock).elements[0].x).toBe(24)
  })

  it('edits a filled region width then height without changing its center or losing the path', async () => {
    const mock = backend()
    const plain = documentFixture()
    plain.fields = []
    plain.modifiers = []
    Object.assign(plain.elements[0], {
      id: 'layer-7', type: 'filled_region', x: 10, y: 710, width: 20, height: 20,
      base_x: 10, base_y: 710, base_width: 20, base_height: 20,
      source_transform: 'translate(0 700)', path_data: 'M0 0H20V20H0Z',
    })
    const canvas = await open(plain)
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="layer-7"]')!, { button: 0 })
    const width = screen.getByRole('spinbutton', { name: '宽度 mm' })
    fireEvent.change(width, { target: { value: '30' } })
    fireEvent.blur(width)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(2))
    expect(lastDocument(mock).elements[0]).toMatchObject({ x: 10, y: 710, width: 30, height: 20 })
    expect(canvas.querySelector('[data-element-id="layer-7"] path')).toBeInTheDocument()
    const height = screen.getByRole('spinbutton', { name: '高度 mm' })
    await waitFor(() => expect(height).toBeEnabled())
    fireEvent.change(height, { target: { value: '25' } })
    fireEvent.blur(height)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(3))
    expect(lastDocument(mock).elements[0]).toMatchObject({ x: 10, y: 710, width: 30, height: 25 })
    expect(canvas.querySelector('[data-element-id="layer-7"] path')).toBeInTheDocument()
  })

  it('commits Modifier mapping and enable without changing modifier order', async () => {
    const mock = backend()
    await open()
    const mapping = screen.getByRole('spinbutton', { name: '最大输出' })
    fireEvent.change(mapping, { target: { value: '2.5' } })
    fireEvent.blur(mapping)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(2))
    expect(lastDocument(mock).modifiers.map((item) => item.id)).toEqual(['size-1'])
    expect(lastDocument(mock).modifiers[0].mapping.max_output).toBe(2.5)
    fireEvent.click(screen.getByRole('checkbox', { name: /尺寸 · size-1/ }))
    await waitFor(() => expect(evaluations(mock)).toHaveLength(3))
    expect(lastDocument(mock).modifiers[0].enabled).toBe(false)
  })

  it('does not commit browser-only zoom, pan, selection or pending slider drafts', async () => {
    const mock = backend()
    const canvas = await open()
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    fireEvent.click(screen.getByRole('button', { name: '缩小' }))
    fireEvent.pointerDown(canvas.querySelector('[data-element-id]')!, { button: 0 })
    fireEvent.change(screen.getByRole('slider', { name: '波长滑杆' }), { target: { value: '75' } })
    expect(evaluations(mock)).toHaveLength(1)
    expect(screen.getByText('revision 0')).toBeInTheDocument()
  })

  it('retains last valid geometry and rolls back document/history on Evaluate failure', async () => {
    const mock = backend(1)
    const canvas = await open()
    const slider = screen.getByRole('slider', { name: '波长滑杆' })
    fireEvent.change(slider, { target: { value: '70' } })
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(evaluations(mock)).toHaveLength(2))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(1)
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
  })

  it('loads the actual 144-element fixed pattern through the project import and mm mapping', async () => {
    const mock = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadFixture('../../work/foundation0/test_dot_grid/document.pattern.json')
    expect(await screen.findByRole('dialog', { name: '设置毫米映射' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('1 SVG 单位对应多少 mm'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: '按此比例打开' }))
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(144))
    expect(evaluations(mock)).toHaveLength(1)
  })

  it('loads the physically printed pattern and exposes its existing Field and Modifier', async () => {
    const mock = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    uploadFixture('../../work/physical-validation-02/physical_validation_02_real_pattern.pattern.json')
    const canvas = await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(3))
    expect(screen.getByRole('region', { name: '参数场' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '效果堆栈' })).toBeInTheDocument()
    expect(evaluations(mock)).toHaveLength(1)
  })
})
