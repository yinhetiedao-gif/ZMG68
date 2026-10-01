import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { ParameterDefinition } from './document/parameterSchema'

vi.mock('./manufacturing/ThreePreview', () => ({
  ThreePreview: ({ resultId }: { resultId: string }) => <div aria-label="三维模型预览">GLB {resultId}</div>,
}))

const parameter = (id: string, value: number, min: number): ParameterDefinition => ({
  id, label: id === 'thickness_mm' ? '厚度' : id, type: 'number', default: value, value, min, max: 10000,
  step: .1, unit: 'mm', options: [],
})
const definitions = { schema_version: '1.0', units: 'mm', definitions: { layout: {}, field: {}, modifier: {},
  fabric_base: { solid: { label: 'Solid', parameters: [parameter('thickness_mm', .6, .01), parameter('margin_mm', 0, 0)] },
    grid: { label: 'Grid', parameters: [parameter('thickness_mm', .6, .01), parameter('margin_mm', 0, 0),
      parameter('spacing_x_mm', 5, .01), parameter('spacing_y_mm', 5, .01), parameter('line_width_mm', 1, .01)] } },
} }
const document = { schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm', mm_per_unit: 1 },
  reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
  elements: [{ id: 'area', type: 'rect', x: 25, y: 20, width: 50, height: 40, rotation: 0, visible: true }] }
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response

describe('F1 Web Fabric Base', () => {
  it('uses generic controls, commits one revision per edit, and builds with matching thickness', async () => {
    const builds: Record<string, unknown>[] = []
    const calls = vi.fn<typeof fetch>((url, init) => {
      const path = String(url)
      if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
      if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm', parameter_definitions: definitions }))
      const body = JSON.parse(String(init?.body)) as Record<string, any>
      if (path.endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: body.document_id,
        document_revision: body.document_revision, recommended_family: null, confidence: 0, analysis_status: 'no_match' }))
      if (path.endsWith('/evaluate')) return Promise.resolve(reply({ schema_version: '1.0', document_id: body.document_id,
        document_revision: body.document_revision, geometry: body.document.document.elements.map((element: object) => ({ ...element, units: 'mm' })),
        bounds_mm: { min_x: 0, min_y: 0, max_x: 50, max_y: 40, width: 50, height: 40, units: 'mm' }, warnings: [] }))
      if (path.endsWith('/manufacturing/build')) {
        builds.push(body)
        return Promise.resolve(reply({ schema_version: '1.0', status: 'completed', manufacturing_result_id: 'fabric-1',
          document_id: body.document_id, document_revision: body.document_revision,
          geometry_validation_summary: { checked_count: 1, error_count: 0, warning_count: 0, issues: [] },
          connectivity_summary: { component_count: 1, isolated_count: 0 },
          conversion_summary: { input_count: 1, converted_count: 1, skipped_count: 0, warnings: [] },
          mesh_validation_summary: { is_watertight: true, component_count: 1, error_count: 0, warning_count: 0, issues: [] },
          component_count: 1, bounds_mm: { size_x: 50, size_y: 40, size_z: body.height_mm, units: 'mm' }, warnings: [] }))
      }
      return Promise.reject(new Error(`unexpected ${path}`))
    })
    vi.stubGlobal('fetch', calls)
    render(<App />)
    await screen.findByText('Backend Online')
    const raw = JSON.stringify(document)
    const file = new File([raw], 'fabric.pattern.json', { type: 'application/json' })
    Object.defineProperty(file, 'text', { value: async () => raw })
    fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
    await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.change(screen.getByLabelText('Fabric Base 类型'), { target: { value: 'solid' } })
    await screen.findByText('revision 1')
    expect(screen.getByLabelText('厚度 (mm)')).toBeInTheDocument()
    const thickness = screen.getByLabelText('厚度 (mm)')
    fireEvent.change(thickness, { target: { value: '0.8' } })
    expect(screen.getByText(/待提交/)).toBeInTheDocument()
    fireEvent.blur(thickness)
    await screen.findByText('revision 2')
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    await screen.findByText('模型已生成')
    expect(builds).toHaveLength(1)
    expect(builds[0].height_mm).toBe(.8)
    expect((builds[0].document as Record<string, any>).document.metadata.fabric_config.base).toMatchObject({ type: 'solid', thickness_mm: .8 })
    expect(screen.getByRole('button', { name: '3D 预览' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Fabric Base 类型'), { target: { value: 'grid' } })
    await screen.findByText('revision 3')
    expect(screen.getByLabelText('spacing_x_mm')).toBeInTheDocument()
    expect(screen.getByText('结果已过期，请重新检查并生成')).toBeInTheDocument()
    await waitFor(() => expect(calls.mock.calls.filter(([url]) => String(url).endsWith('/evaluate'))).toHaveLength(4))
  })
})
