import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { PatternDocumentDTO } from './model/types'
import basicGrid from './examples/fixtures/basic-grid.pattern.json'

const draftMocks = vi.hoisted(() => ({ save: vi.fn(), load: vi.fn(), clear: vi.fn(),
  saveBefore: vi.fn(), loadBefore: vi.fn() }))
vi.mock('./draft/localDraft', () => ({ saveDraft: draftMocks.save, loadDraft: draftMocks.load,
  clearDraft: draftMocks.clear, saveBeforeExampleDraft: draftMocks.saveBefore,
  loadBeforeExampleDraft: draftMocks.loadBefore }))

const parameter = (id: string, label: string, value: number, integer = false) => ({
  id, label, type: integer ? 'integer' : 'number', default: value, value, min: 1, max: 100,
  step: 1, unit: integer ? '' : 'mm', options: [],
})
const catalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: { grid: { label: '规则矩阵', parameters: [parameter('rows', '行数', 3, true),
    parameter('columns', '列数', 3, true), parameter('spacing_x', '横向间距', 16),
    parameter('spacing_y', '纵向间距', 16), parameter('element_width', '单元尺寸', 8)] } },
  field: { linear: { label: '线性场', parameters: [{ ...parameter('angle', '角度', 0), min: -180, max: 180 },
    parameter('start', '起点', 16), parameter('end', '终点', 64)] } },
  modifier: { size: { label: '尺寸', parameters: [{ ...parameter('min_output', '最小尺寸', .5), min: 0, max: 3 },
    { ...parameter('max_output', '最大尺寸', 1.5), min: 0, max: 3 }] },
  rotation: { label: '旋转', parameters: [{ ...parameter('min_output', '最小角度', -45), min: -180, max: 180 },
    { ...parameter('max_output', '最大角度', 45), min: -180, max: 180 }] } },
} }

function backend() {
  const evaluations: PatternDocumentDTO[] = []
  const response = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    if (path.endsWith('/health')) return Promise.resolve(response({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(response({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog }))
    if (path.endsWith('/assets')) return Promise.resolve(response({ asset_id: 'uploaded-image' }))
    if (path.endsWith('/import')) return Promise.resolve(response({ schema_version: '1.0', document_id: 'new-image',
      document_revision: 0, assets: [], document: { ...structuredClone(basicGrid),
        metadata: { web_import_scale_unconfirmed: true } } }))
    const dto = (JSON.parse(String(init?.body)) as { document: PatternDocumentDTO }).document
    if (path.endsWith('/manufacturing/build')) return Promise.resolve(response({
      schema_version: '1.0', status: 'completed', manufacturing_result_id: `mesh-${dto.document_revision}`,
      document_id: dto.document_id, document_revision: dto.document_revision,
      geometry_validation_summary: { checked_count: dto.document.elements.length, error_count: 0, warning_count: 0, issues: [] },
      connectivity_summary: { component_count: 1, isolated_count: 0 },
      conversion_summary: { input_count: dto.document.elements.length, converted_count: dto.document.elements.length,
        skipped_count: 0, warnings: [] },
      mesh_validation_summary: { is_watertight: true, component_count: 1, error_count: 0, warning_count: 0, issues: [] },
      component_count: 1, bounds_mm: { size_x: 40 * Number(dto.document.canvas.mm_per_unit ?? 1),
        size_y: 40 * Number(dto.document.canvas.mm_per_unit ?? 1), size_z: 2, units: 'mm' }, warnings: [],
    }))
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(response({ document_id: dto.document_id,
      document_revision: dto.document_revision, recommended_family: 'grid', confidence: .98, analysis_status: 'matched' }))
    evaluations.push(dto)
    return Promise.resolve(response({ schema_version: '1.0', document_id: dto.document_id,
      document_revision: dto.document_revision, geometry: dto.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 10, min_y: 10, max_x: 50, max_y: 50,
        width: 40 * Number(dto.document.canvas.mm_per_unit ?? 1),
        height: 40 * Number(dto.document.canvas.mm_per_unit ?? 1), units: 'mm' }, warnings: [] }))
  }))
  return evaluations
}

async function openFromEmpty(title: string) {
  fireEvent.click(screen.getByRole('button', { name: '试用示例' }))
  expect(screen.getAllByText('支持标准二维 STL')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: `打开示例：${title}` }))
  await screen.findByLabelText('最终二维几何，单位毫米')
}

describe('P1 built-in examples', () => {
  beforeEach(() => {
    draftMocks.save.mockReset().mockImplementation(async (dto: PatternDocumentDTO, fileName: string | null,
      sourceAsset: unknown) => ({ dto, file_name: fileName, source_asset: sourceAsset }))
    draftMocks.load.mockReset().mockResolvedValue(null)
    draftMocks.saveBefore.mockReset().mockImplementation(async (dto: PatternDocumentDTO, fileName: string | null,
      sourceAsset: unknown, uiState: { pending_layout: unknown }) => ({ dto, file_name: fileName,
      source_asset: sourceAsset, pending_layout: uiState?.pending_layout }))
    draftMocks.loadBefore.mockReset().mockResolvedValue(null)
    draftMocks.clear.mockReset().mockResolvedValue(undefined)
  })

  it('loads editable Grid, resets as one commit, and Undo/Redo restores edits', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    expect(screen.getByRole('button', { name: '导入自己的图案' })).toBeEnabled()
    await openFromEmpty('基础圆点阵列')
    expect(evaluations).toHaveLength(1)
    expect(evaluations[0].document.elements).toHaveLength(9)
    const rows = screen.getByLabelText('行数')
    fireEvent.change(rows, { target: { value: '4' } })
    fireEvent.blur(rows)
    expect(evaluations).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await waitFor(() => expect(evaluations).toHaveLength(2))
    expect((evaluations[1].document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(4)
    fireEvent.click(screen.getByRole('button', { name: '恢复示例初始状态' }))
    await waitFor(() => expect(evaluations).toHaveLength(3))
    expect(evaluations[2].document_revision).toBe(2)
    expect((evaluations[2].document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(3)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(evaluations).toHaveLength(4))
    expect((evaluations[3].document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(4)
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(evaluations).toHaveLength(5))
    expect((evaluations[4].document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(3)
  })

  it.each(['基础圆点阵列', '参数渐变'])('manufactures the unchanged %s example through the standard Web flow', async (title) => {
    backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty(title)
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith('/manufacturing/build'))!
    const payload = JSON.parse(String(call[1]?.body)) as { document_id: string; document_revision: number;
      document: PatternDocumentDTO }
    expect(payload.document_id).toBe(payload.document.document_id)
    expect(payload.document_revision).toBe(0)
    expect(payload.document.document_revision).toBe(0)
  })

  it('opens the gradient example with its shared field and modifier controls visible', async () => {
    backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('参数渐变')
    expect(screen.getByText('调整线性场的方向和范围，观察尺寸与旋转如何渐变。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /LAYOUT \/ 规则矩阵/ })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'FIELD / 参数场' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'MODIFIERS / 效果堆栈' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('尺寸 · size-1')).toBeInTheDocument()
    expect(screen.getByText('旋转 · rotation-1')).toBeInTheDocument()
  })

  it('confirms proportional 60 × 60 mm sizing, then builds from that revision', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('基础圆点阵列')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    expect(screen.getByText(/当前尺寸：40 × 40 mm/)).toBeInTheDocument()
    expect(screen.getByText('未确认')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('spinbutton', { name: '真实宽度 mm' }), { target: { value: '60' } })
    expect(screen.getByRole('spinbutton', { name: '真实高度 mm' })).toHaveValue(60)
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认尺寸' }))
    await screen.findByText('revision 1')
    await screen.findByText('已确认')
    expect(evaluations[1].document.canvas.mm_per_unit).toBe(1.5)
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(await screen.findByText('60 × 60 × 2 mm')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
  })

  it('manufactures the basic Grid after Apply Layout', async () => {
    backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('基础圆点阵列')
    const rows = screen.getByLabelText('行数')
    fireEvent.change(rows, { target: { value: '4' } })
    fireEvent.blur(rows)
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await screen.findByText('revision 1')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith('/manufacturing/build'))!
    const payload = JSON.parse(String(call[1]?.body)) as { document_revision: number; document: PatternDocumentDTO }
    expect(payload.document_revision).toBe(1)
    expect(payload.document.document_revision).toBe(1)
    expect((payload.document.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(4)
  })

  it('manufactures the original gradient after an edit and Reset Example commit', async () => {
    backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('参数渐变')
    const angle = screen.getByRole('spinbutton', { name: /^角度/ })
    fireEvent.change(angle, { target: { value: '25' } })
    fireEvent.blur(angle)
    await screen.findByText('revision 1')
    fireEvent.click(screen.getByRole('button', { name: '恢复示例初始状态' }))
    await screen.findByText('revision 2')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    const calls = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/manufacturing/build'))
    expect(calls).toHaveLength(1)
    const payload = JSON.parse(String(calls[0][1]?.body)) as { document_revision: number; document: PatternDocumentDTO }
    expect(payload.document_revision).toBe(2)
    expect(payload.document.document_revision).toBe(2)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
  })

  it('protects the current draft before opening a second example and blocks on save failure', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('基础圆点阵列')
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：参数渐变' }))
    await waitFor(() => expect(evaluations).toHaveLength(2))
    expect(draftMocks.save).toHaveBeenCalledWith(evaluations[0], '基础圆点阵列', null,
      { pending_layout: null, example_session_active: false })
    expect(evaluations[1].document.fields[0].type).toBe('linear')
    expect(evaluations[1].document.modifiers.map((item) => item.type)).toEqual(['size', 'rotation'])
    draftMocks.save.mockRejectedValueOnce(new Error('草稿写入失败'))
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await screen.findByText(/当前作品保存失败，已取消切换：草稿写入失败/)
    expect(evaluations).toHaveLength(2)
    expect(screen.getByLabelText('当前项目')).toHaveTextContent('参数渐变')
  })

  it('edits the gradient through the existing Field and Modifier parameter panels', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('参数渐变')
    expect(evaluations[0].document.fields[0].type).toBe('linear')
    expect(evaluations[0].document.modifiers.map((item) => item.type)).toEqual(['size', 'rotation'])
    const angle = screen.getByRole('spinbutton', { name: /^角度/ })
    fireEvent.change(angle, { target: { value: '25' } })
    fireEvent.blur(angle)
    await waitFor(() => expect(evaluations).toHaveLength(2))
    expect(evaluations[1].document.fields[0].parameters).toMatchObject({ angle: 25 })
    const sizeMax = screen.getByRole('spinbutton', { name: /^最大尺寸/ })
    fireEvent.change(sizeMax, { target: { value: '2' } })
    fireEvent.blur(sizeMax)
    await waitFor(() => expect(evaluations).toHaveLength(3))
    expect(evaluations[2].document.modifiers[0].mapping).toMatchObject({ max_output: 2 })
  })

  it('keeps a separate recoverable copy when replacing an imported work with an example', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    const document = { schema_version: 1, canvas: { width: 60, height: 60, unit: 'mm', mm_per_unit: 1 },
      reference: { source_path: '', visible: false }, elements: [
        { id: 'work-1', type: 'circle', x: 20, y: 20, width: 6, height: 6, rotation: 0, visible: true }],
      groups: [], transforms: {}, metadata: {}, fields: [], modifiers: [] }
    const json = JSON.stringify(document)
    const file = new File([json], 'my-work.pattern.json', { type: 'application/json' })
    Object.defineProperty(file, 'text', { value: async () => json })
    fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
    await screen.findByLabelText('最终二维几何，单位毫米')
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(evaluations).toHaveLength(2))
    expect(draftMocks.save).toHaveBeenCalledWith(evaluations[0], 'my-work.pattern.json', null,
      { pending_layout: null, example_session_active: false })
    expect(draftMocks.saveBefore).toHaveBeenCalledWith(evaluations[0], 'my-work.pattern.json', null,
      { pending_layout: null, example_session_active: false })
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(evaluations).toHaveLength(3))
    expect(evaluations[2].document.elements[0].id).toBe('work-1')
  })

  it('keeps the original work across multiple edited examples, then ends the example session on return', async () => {
    const evaluations = backend()
    render(<App />)
    await screen.findByText('Backend Online')
    const original = structuredClone(basicGrid)
    delete (original.metadata as Record<string, unknown>)['xiaomang_pattern_lab.example_id']
    const raw = JSON.stringify(original)
    const file = new File([raw], 'my-work.pattern.json', { type: 'application/json' })
    Object.defineProperty(file, 'text', { value: async () => raw })
    fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
    await screen.findByLabelText('最终二维几何，单位毫米')
    fireEvent.change(screen.getByLabelText('行数'), { target: { value: '5' } })
    fireEvent.blur(screen.getByLabelText('行数'))
    expect(screen.getByText('有未应用修改')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await screen.findByText('正在试用示例：基础圆点阵列')
    fireEvent.change(screen.getByLabelText('行数'), { target: { value: '4' } })
    fireEvent.blur(screen.getByLabelText('行数'))
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await screen.findByText('revision 1')
    fireEvent.click(screen.getByRole('button', { name: /试用示例/ }))
    fireEvent.click(screen.getByRole('button', { name: '打开示例：参数渐变' }))
    await screen.findByText('正在试用示例：参数渐变')
    const angle = screen.getByRole('spinbutton', { name: /^角度/ })
    fireEvent.change(angle, { target: { value: '25' } })
    fireEvent.blur(angle)
    await screen.findByText('revision 1')
    expect(draftMocks.saveBefore).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: '← 返回之前作品' }))
    await waitFor(() => expect(evaluations.at(-1)?.document_id).toBe(evaluations[0].document_id))
    expect(screen.getByLabelText('当前项目')).toHaveTextContent('my-work.pattern.json')
    expect(screen.getByLabelText('行数')).toHaveValue(5)
    expect(screen.getByText('有未应用修改')).toBeInTheDocument()
    expect((evaluations.at(-1)!.document.metadata['xiaomang_pattern_lab.parametric'] as { grid: { rows: number } }).grid.rows).toBe(3)
    expect(screen.queryByRole('button', { name: '← 返回之前作品' })).not.toBeInTheDocument()
  })

  it('does not import over an unsaved example and ends the session after a successful image import', async () => {
    backend()
    render(<App />)
    await screen.findByText('Backend Online')
    await openFromEmpty('基础圆点阵列')
    const file = new File(['png'], 'new-pattern.png', { type: 'image/png' })
    draftMocks.save.mockRejectedValueOnce(new Error('本地空间已满'))
    fireEvent.drop(screen.getByLabelText('中央工作区').querySelector('.canvas-stage')!, {
      dataTransfer: { files: [file] },
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('当前作品保存失败，已取消切换')
    expect(screen.getByLabelText('当前项目')).toHaveTextContent('基础圆点阵列')
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/assets'))).toHaveLength(0)
    fireEvent.drop(screen.getByLabelText('中央工作区').querySelector('.canvas-stage')!, {
      dataTransfer: { files: [file] },
    })
    await waitFor(() => expect(screen.getByLabelText('当前项目')).toHaveTextContent('new-pattern.png'))
    expect(screen.queryByText(/正在试用示例/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '← 返回之前作品' })).not.toBeInTheDocument()
  })
})
