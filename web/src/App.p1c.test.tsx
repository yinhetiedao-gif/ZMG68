import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

function response(value: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => value } as Response
}

const fieldParameter = (id: string, label: string, value: number) => ({
  id, label, type: 'number', default: value, value, min: 0, max: 100,
  step: 1, unit: '', options: [],
})
const catalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: { free: { label: '自由布局', parameters: [] } },
  field: {
    wave: { label: '波浪场', parameters: [fieldParameter('wavelength', '波长', 40)] },
    noise: { label: '有机噪声', parameters: [fieldParameter('scale', '尺度', 50)] },
  }, modifier: {},
} }

function fixture() {
  return { schema_version: '1.0', document_id: 'p1c', document_revision: 0, assets: [],
    document: { schema_version: 1, canvas: { width: 100, height: 100, unit: 'mm', mm_per_unit: 1 },
      reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {},
      elements: [
        { id: 'a', type: 'circle', x: 10, y: 10, width: 4, height: 4, rotation: 0, visible: true },
        { id: 'b', type: 'circle', x: 60, y: 10, width: 4, height: 4, rotation: 0, visible: true },
      ],
      fields: [{ id: 'wave-1', type: 'wave', parameters: { wavelength: 40 } }],
      modifiers: [{ id: 'size-1', type: 'size', field_id: 'wave-1', enabled: true,
        mapping: { min_output: .5, max_output: 1.5, strength: 1, falloff: 1 } }],
    } }
}

function backend() {
  const calls: { path: string; body: Record<string, unknown> }[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {}
    calls.push({ path, body })
    if (path.endsWith('/health')) return Promise.resolve(response({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(response({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog }))
    if (path.endsWith('/analyze-pattern')) {
      const dto = body.document as ReturnType<typeof fixture>
      return Promise.resolve(response({ document_id: dto.document_id, document_revision: dto.document_revision,
        recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
    }
    const dto = body.document as ReturnType<typeof fixture>
    return Promise.resolve(response({ schema_version: '1.0', document_id: dto.document_id,
      document_revision: dto.document_revision,
      geometry: dto.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 8, min_y: 8, max_x: 62, max_y: 12, width: 54, height: 4, units: 'mm' }, warnings: [] }))
  }))
  return calls
}

async function open() {
  render(<App />)
  await screen.findByText('Backend Online')
  const json = JSON.stringify(fixture().document)
  const file = new File([json], 'field.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => json })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await waitFor(() => expect(screen.getByRole('button', { name: '＋ 添加参数场' })).toBeEnabled())
  await waitFor(() => expect(screen.getByRole('slider', { name: '波长滑杆' })).toBeEnabled())
}

const evaluations = (calls: ReturnType<typeof backend>) => calls.filter((item) => item.path.endsWith('/evaluate'))

describe('P1-C Web Field System', () => {
  it('adds, binds, edits, disables and protects a field in single commits', async () => {
    const calls = backend()
    await open()
    fireEvent.change(screen.getByLabelText('参数场类型'), { target: { value: 'noise' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ 添加参数场' }))
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(evaluations(calls)).toHaveLength(2)
    const addDto = evaluations(calls)[1].body.document as PatternDocumentDTO
    expect(addDto.document.fields.at(-1)).toMatchObject({ id: 'field-1', type: 'noise', parameters: { scale: 50 } })
    expect(addDto.document.modifiers).toEqual(fixture().document.modifiers)
    expect(addDto.document.elements).toEqual(fixture().document.elements)

    await waitFor(() => expect(screen.getByRole('slider', { name: '尺度滑杆' })).toBeEnabled())
    const slider = screen.getByRole('slider', { name: '尺度滑杆' })
    fireEvent.change(slider, { target: { value: '60' } })
    fireEvent.change(slider, { target: { value: '70' } })
    expect(evaluations(calls)).toHaveLength(2)
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(evaluations(calls)).toHaveLength(3))
    expect(((evaluations(calls)[2].body.document as PatternDocumentDTO).document.fields.at(-1)?.parameters as Record<string, unknown>).scale).toBe(70)

    await waitFor(() => expect(screen.getByLabelText('驱动参数场')).toBeEnabled())
    fireEvent.change(screen.getByLabelText('驱动参数场'), { target: { value: 'field-1' } })
    await waitFor(() => expect(evaluations(calls)).toHaveLength(4))
    fireEvent.click(screen.getByRole('button', { name: '删除参数场' }))
    await screen.findByText('该参数场仍被效果层引用，请先更换效果层的参数场。')
    expect(evaluations(calls)).toHaveLength(4)
    fireEvent.click(screen.getByRole('checkbox', { name: '启用参数场' }))
    await waitFor(() => expect(evaluations(calls)).toHaveLength(5))
    expect((evaluations(calls)[4].body.document as PatternDocumentDTO).document.fields.at(-1)?.enabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluations(calls)).toHaveLength(6))
    expect((evaluations(calls)[5].body.document as PatternDocumentDTO).document.fields.at(-1)?.enabled).toBe(true)
  })
})
