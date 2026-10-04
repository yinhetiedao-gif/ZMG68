import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'

const number = (id: string, label: string, value: number, min = -100, max = 100) => ({
  id, label, type: 'number', default: value, value, min, max, step: 1, unit: '', options: [],
})
const catalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: { free: { label: '自由布局', parameters: [] } },
  field: { wave: { label: '波浪场', parameters: [number('wavelength', '波长', 40, .01, 100)] } },
  modifier: {
    size: { label: '尺寸', parameters: [number('min_output', '最小输出', .5, 0), number('max_output', '最大输出', 1.5, 0)] },
    rotation: { label: '旋转', parameters: [number('min_output', '最小输出', -30), number('max_output', '最大输出', 30)] },
    position: { label: '位置／变形', parameters: [
      { id: 'mode', label: '变形方式', type: 'select', default: 'offset', value: 'offset', min: null, max: null,
        step: null, unit: '', options: [{ value: 'offset', label: '整体偏移' }, { value: 'twist', label: '扭曲' }] },
      number('offset_x', '偏移 X', 0), number('offset_y', '偏移 Y', 0),
      number('center_x', '中心 X', 0), number('center_y', '中心 Y', 0), number('angle', '角度', 30),
      number('radius', '作用半径', 100, .01, 1000), number('strength', '强度', 1, 0, 1),
      number('falloff', '衰减', 1, .01, 20),
    ] },
  },
} }

function fixture() {
  return { schema_version: 1, canvas: { width: 100, height: 100, unit: 'mm', mm_per_unit: 1 },
    reference: { source_path: '', visible: false }, groups: [], transforms: {},
    elements: [{ id: 'a', type: 'circle', x: 10, y: 10, width: 4, height: 4, rotation: 0, visible: true }],
    fields: [{ id: 'wave-1', type: 'wave', parameters: { wavelength: 40 } }], modifiers: [],
    metadata: { 'xiaomang_pattern_lab.placement_assignment': {
      enabled: true, shape_prototypes: { circle: {}, star: {} }, replacement_map: {},
    } },
  }
}

function backend() {
  const requests: { path: string; dto?: PatternDocumentDTO }[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    const body = init?.body ? JSON.parse(String(init.body)) as { document: PatternDocumentDTO } : null
    requests.push({ path, dto: body?.document })
    const response = (value: unknown): Response => ({ ok: true, status: 200, json: async () => value }) as Response
    if (path.endsWith('/health')) return Promise.resolve(response({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(response({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog }))
    const dto = body!.document
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(response({ document_id: dto.document_id,
      document_revision: dto.document_revision, recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
    return Promise.resolve(response({ schema_version: '1.0', document_id: dto.document_id,
      document_revision: dto.document_revision,
      geometry: dto.document.elements.map((item) => ({ ...item, units: 'mm' })),
      bounds_mm: { min_x: 8, min_y: 8, max_x: 12, max_y: 12, width: 4, height: 4, units: 'mm' }, warnings: [] }))
  }))
  return requests
}

const evaluations = (requests: ReturnType<typeof backend>) => requests.filter((request) => request.path.endsWith('/evaluate'))
const latest = (requests: ReturnType<typeof backend>) => evaluations(requests).at(-1)!.dto!

async function open() {
  render(<App />)
  await screen.findByText('Backend Online')
  const json = JSON.stringify(fixture())
  const file = new File([json], 'p1d.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => json })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await waitFor(() => expect(screen.getByRole('button', { name: '＋ 尺寸' })).toBeEnabled())
  await waitFor(() => expect(screen.getByRole('button', { name: '＋ 位置/变形' })).toBeEnabled())
}

describe('P1-D Web Modifier Stack', () => {
  it('adds Size and Rotation with one shared Field, preserves order, and removes as one Undo', async () => {
    const requests = backend()
    await open()
    fireEvent.click(screen.getByRole('button', { name: '＋ 尺寸' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(2))
    fireEvent.click(screen.getByRole('button', { name: '＋ 旋转' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(3))
    expect(latest(requests).document.modifiers.map((item) => [item.type, item.field_id]))
      .toEqual([['size', 'wave-1'], ['rotation', 'wave-1']])
    expect(latest(requests).document.elements).toEqual(fixture().elements)
    fireEvent.click(screen.getByRole('checkbox', { name: '旋转' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(4))
    expect(latest(requests).document.modifiers[1].enabled).toBe(false)
    fireEvent.click(screen.getAllByRole('button', { name: '删除效果层' })[0])
    await waitFor(() => expect(evaluations(requests)).toHaveLength(5))
    expect(latest(requests).document.modifiers.map((item) => item.type)).toEqual(['rotation'])
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(6))
    expect(latest(requests).document.modifiers.map((item) => item.type)).toEqual(['size', 'rotation'])
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(7))
    expect(latest(requests).document.modifiers.map((item) => item.type)).toEqual(['rotation'])
  })

  it('keeps Position slider transient, commits once, and reuses existing shape replacement', async () => {
    const requests = backend()
    await open()
    fireEvent.click(screen.getByRole('button', { name: '＋ 位置/变形' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(2))
    const slider = screen.getByRole('slider', { name: '偏移 X滑杆' })
    fireEvent.change(slider, { target: { value: '8' } })
    fireEvent.change(slider, { target: { value: '12' } })
    expect(evaluations(requests)).toHaveLength(2)
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(evaluations(requests)).toHaveLength(3))
    const stack = latest(requests).document.metadata['xiaomang_pattern_lab.shared_modifiers'] as {
      source_elements: unknown[]; modifiers: Array<{ parameters: { offset_x: number } }>
    }
    expect(stack.modifiers[0].parameters.offset_x).toBe(12)
    expect(stack.source_elements).toEqual(fixture().elements)
    expect(latest(requests).document.elements).toEqual(fixture().elements)
    expect(latest(requests).document_revision).toBe(2)
    fireEvent.click(screen.getByRole('checkbox', { name: '位置/变形' }))
    await waitFor(() => expect(evaluations(requests)).toHaveLength(4))
    expect(((latest(requests).document.metadata['xiaomang_pattern_lab.shared_modifiers'] as {
      modifiers: Array<{ enabled: boolean }>
    }).modifiers[0].enabled)).toBe(false)
    const canvas = screen.getByRole('img', { name: '最终二维几何，单位毫米' })
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="a"]')!, { button: 0 })
    fireEvent.change(screen.getByLabelText('形状替换 · a'), { target: { value: 'star' } })
    await waitFor(() => expect(evaluations(requests)).toHaveLength(5))
    expect((latest(requests).document.metadata['xiaomang_pattern_lab.placement_assignment'] as {
      replacement_map: Record<string, string>
    }).replacement_map.a).toBe('star')
  })
})
