import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { ParameterDefinition } from './document/parameterSchema'

vi.mock('./manufacturing/ThreePreview', () => ({
  ThreePreview: ({ resultId }: { resultId: string }) => <div aria-label="三维模型预览">GLB {resultId}</div>,
}))
vi.mock('./manufacturing/FabricThreePreview', () => ({
  FabricThreePreview: ({ plan }: { plan: { total_count: number } }) => <div aria-label="Fabric 设计预览">{plan.total_count} instances</div>,
}))

const parameter = (id: string, value: number, min: number): ParameterDefinition => ({
  id, label: id === 'thickness_mm' ? '厚度' : id, type: 'number', default: value, value, min, max: 10000,
  step: .1, unit: 'mm', options: [],
})
const definitions = { schema_version: '1.0', units: 'mm', definitions: { layout: {}, field: {}, modifier: {},
  fabric_base: { solid: { label: 'Solid', parameters: [parameter('thickness_mm', .6, .01), parameter('margin_mm', 0, 0)] },
    grid: { label: 'Grid', parameters: [parameter('thickness_mm', .6, .01), parameter('margin_mm', 0, 0),
      parameter('spacing_x_mm', 5, .01), parameter('spacing_y_mm', 5, .01), parameter('line_width_mm', 1, .01)] } },
  fabric_cell: Object.fromEntries(['cylinder', 'cone', 'pyramid', 'double_tower', 'fin'].map((type) => [type,
    { label: type, parameters: [parameter('width_mm', 2, .01), parameter('depth_mm', 2, .01), parameter('height_mm', 3, .01)] }])),
  fabric_placement: { regular: { label: 'regular', parameters: [parameter('spacing_x_mm', 5, .01), parameter('spacing_y_mm', 5, .01)] } },
} }
const document = { schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm', mm_per_unit: 1 },
  reference: { source_path: '', visible: false }, groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [],
  elements: [{ id: 'area', type: 'rect', x: 25, y: 20, width: 50, height: 40, rotation: 0, visible: true }] }
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response

describe('F1 Web Fabric Base', () => {
  it('uses generic controls and previews without entering manufacturing or enabling Fabric STL', async () => {
    const builds: Record<string, unknown>[] = []
    const previews: Record<string, any>[] = []
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
      if (path.endsWith('/fabric/preview')) {
        previews.push(body)
        return Promise.resolve(reply({ schema_version: '1.0', kind: 'fabric_instance_preview',
          document_id: body.document.document_id, document_revision: body.document_revision,
          preview_id: `preview-${body.document_revision}`, placement_mode: 'area_fill', unit_size_mode: 'follow_pattern', element_count: 1,
          count: 1, active_count: 1, total_count: 1, skipped_count: 0, unmatched_reference_count: 0,
          preview_simplified: false,
          prototype: null, instances: [{ id: 'preview-1', x_mm: 25, y_mm: 20, z_mm: .8,
            rotation_deg: 0, scale: 1, scale_x: 1, scale_y: 1, enabled: true,
            cell_type: 'cone', base_width_mm: 2, base_depth_mm: 2, base_height_mm: 3, height_mm: 3,
            cell_width_mm: 2, cell_depth_mm: 2, cell_height_mm: 3,
            source_id: null, final_geometry_id: null }], base_preview: { type: 'solid', bounds_mm: [0, 0, 50, 40],
            thickness_mm: .8, spacing_x_mm: null, spacing_y_mm: null, line_width_mm: null },
          timings_ms: { evaluate: 1, plan_and_prototype: 1 }, cache_hit: false }))
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
    fireEvent.click(screen.getByRole('button', { name: '更新3D预览' }))
    await screen.findByText('设计预览已就绪')
    expect(builds).toHaveLength(0)
    expect(previews).toHaveLength(1)
    expect(previews[0].document.document.metadata.fabric_config.base).toMatchObject({ type: 'solid', thickness_mm: .8 })
    expect(screen.getByRole('button', { name: '3D 预览' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Fabric STL 尚未开放' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Fabric Base 类型'), { target: { value: 'grid' } })
    await screen.findByText('revision 3')
    expect(screen.getByLabelText('spacing_x_mm')).toBeInTheDocument()
    expect(screen.getByText('设计已变化，请更新3D预览')).toBeInTheDocument()
    await waitFor(() => expect(calls.mock.calls.filter(([url]) => String(url).endsWith('/evaluate'))).toHaveLength(4))
    fireEvent.change(screen.getByLabelText('Unit Cell 类型'), { target: { value: 'cylinder' } })
    await screen.findByText('revision 4')
    expect(screen.getByText(/Fabric 单元当前用于设计与 3D 预览；最终 Fabric STL 尚未开放/)).toBeInTheDocument()
    const cellControls = within(screen.getByLabelText('Fabric Unit Cell'))
    fireEvent.change(cellControls.getByLabelText('height_mm'), { target: { value: '4' } })
    fireEvent.blur(cellControls.getByLabelText('height_mm'))
    await screen.findByText('revision 5')
    fireEvent.change(cellControls.getByLabelText('spacing_x_mm'), { target: { value: '6' } })
    fireEvent.blur(cellControls.getByLabelText('spacing_x_mm'))
    await screen.findByText('revision 6')
    fireEvent.click(screen.getByRole('button', { name: '更新3D预览' }))
    await screen.findByText('设计预览已就绪')
    expect(builds).toHaveLength(0)
    const fabric = previews[1].document.document.metadata.fabric_config
    expect(fabric.unit_cell).toMatchObject({ type: 'cylinder', height_mm: 4 })
    expect(fabric.placement.spacing_x_mm).toBe(6)
    fireEvent.click(screen.getByRole('button', { name: /3D Preview/ }))
    expect(await screen.findByText('1 instances')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.change(screen.getByLabelText('Unit Cell 类型'), { target: { value: 'fin' } })
    await screen.findByText('revision 7')
    expect(screen.getByText('设计已变化，请更新3D预览')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('布点方式'), { target: { value: 'pattern_points' } })
    await screen.findByText('revision 8')
    expect(within(screen.getByLabelText('Fabric Unit Cell')).queryByLabelText('spacing_x_mm')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '更新3D预览' }))
    await screen.findByText('设计预览已就绪')
    expect(previews.at(-1)?.document.document.metadata.fabric_config.placement.mode).toBe('pattern_points')
  }, 15000)
})
