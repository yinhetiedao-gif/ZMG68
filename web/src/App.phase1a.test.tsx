import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { phase1aBounds, phase1aCatalog, phase1aDocument } from './test/phase1aFixture'
import { linearCatalog } from './test/linearSizeFixture'
import { createExampleDocument } from './examples/catalog'
import type { PatternDocumentDTO } from './model/types'

vi.mock('./manufacturing/FabricThreePreview', () => ({ FabricThreePreview: ({ plan }: { plan: any }) =>
  <div aria-label="测试共享 Fabric 画面">{plan.instances[0]?.cell_width_mm} / {plan.instances[0]?.height_mm}</div> }))

const drafts = vi.hoisted(() => ({ save: vi.fn(), load: vi.fn(), loadBefore: vi.fn(), saveBefore: vi.fn(), clear: vi.fn() }))
vi.mock('./draft/localDraft', () => ({ saveDraft: drafts.save, loadDraft: drafts.load,
  loadBeforeExampleDraft: drafts.loadBefore, saveBeforeExampleDraft: drafts.saveBefore, clearDraft: drafts.clear }))
beforeEach(() => {
  drafts.save.mockReset().mockResolvedValue({}); drafts.load.mockResolvedValue(null); drafts.loadBefore.mockResolvedValue(null)
})
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
function startBackend(failFirstPreview = false) {
  const evaluated: PatternDocumentDTO[] = []
  let finish!: (response: Response) => void
  const catalog = structuredClone(phase1aCatalog)
  catalog.definitions.modifier = structuredClone(linearCatalog.definitions.modifier)
  catalog.definitions.layout.grid = { label: 'Grid', parameters: [{ id: 'rows', label: '行数', type: 'integer',
    default: 3, value: 3, min: 1, max: 100, step: 1, unit: '', options: [] }] }
  const fetcher = vi.fn<typeof fetch>(async (url, init) => {
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: catalog })
    const body = JSON.parse(String(init?.body))
    if (String(url).endsWith('/evaluate')) {
      evaluated.push(body.document)
      return reply({ schema_version: '1.0', document_id: body.document_id, document_revision: body.document_revision,
        geometry: body.document.document.elements.map((element: object) => ({ ...element, units: 'mm' })),
        bounds_mm: phase1aBounds, warnings: [] })
    }
    if (String(url).endsWith('/analyze-pattern')) return reply({ document_id: body.document_id, document_revision: body.document_revision,
      recommended_family: null, confidence: 0, analysis_status: 'no_match' })
    if (String(url).endsWith('/fusion')) return new Promise<Response>(resolve => { finish = resolve })
    if (String(url).endsWith('/fabric/preview')) {
      if (failFirstPreview) { failFirstPreview = false; return reply({ code: 'staging_busy', message: '测试站正在处理另一项三维任务，请稍后重试。' }, 429) }
      const dto = body.document, config = dto.document.metadata.fabric_config, original = config.shape_source === 'original'
      const cell = original ? { type: 'original_contour', size_mode: 'follow_pattern', width_mm: 60 * config.original_shape.size_scale,
        depth_mm: 60 * config.original_shape.size_scale, height_mm: config.original_shape.height_mm } : config.unit_cell
      return reply({ schema_version: '1.0', kind: 'fabric_instance_preview', document_id: dto.document_id,
        document_revision: dto.document_revision, preview_id: `p-${dto.document_revision}`,
        placement_mode: 'pattern_points', unit_size_mode: cell.size_mode, element_count: 1, output_mode: config.output_mode ?? 'cells_with_base',
        count: 1, active_count: 1, total_count: 1, skipped_count: 0, unmatched_reference_count: 0,
        preview_simplified: false, prototype: null, cache_hit: false,
        ...(original ? { shape_source: 'original', contour_prototypes: { cell: {
          vertices: [[0,0,0],[1,0,0],[0,1,0],[0,0,1]], faces: [[0,2,1],[0,1,3],[0,3,2],[1,2,3]],
        } } } : {}),
        base_preview: { type: 'solid', bounds_mm: [10, 20, 70, 80], thickness_mm: .6 },
        timings_ms: { evaluate: 1, plan_and_prototype: 1, serialization: 1 }, instances: [{
          id: 'cell', source_id: 'square', final_geometry_id: 'square', x_mm: 40, y_mm: 50, z_mm: config.output_mode === 'cells_only' ? 0 : .6,
          rotation_deg: 0, scale: 1, scale_x: 1, scale_y: 1, enabled: true, cell_type: cell.type,
          base_width_mm: cell.width_mm, base_depth_mm: cell.depth_mm, base_height_mm: cell.height_mm,
          cell_width_mm: cell.width_mm, cell_depth_mm: cell.depth_mm, cell_height_mm: cell.height_mm, height_mm: cell.height_mm,
        }] })
    }
    return reply({ code: 'test_unexpected', message: 'unexpected test request' }, 422)
  })
  vi.stubGlobal('fetch', fetcher)
  return { evaluated, fetcher, finish: (response: Response) => finish(response) }
}
async function open(dto = phase1aDocument()) {
  const ui = render(<App />)
  await screen.findByText('Backend Online')
  const raw = JSON.stringify(dto.document)
  const file = new File([raw], 'phase1a.pattern.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => raw })
  fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
  await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
  return ui
}
function expandSection(name: string) {
  const button = screen.getByRole('button', { name })
  if (button.getAttribute('aria-expanded') !== 'true') fireEvent.click(button)
}
function heightSettings(recipe = false) {
  expandSection('高度与变化')
  if (recipe) expandSection('效果预设')
}
const manufacture = () => fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))

describe('Phase 1A real editor connections', () => {
  it('R1 default original-shape busy preview has one error and an explicit same-input retry', async () => {
    const backend = startBackend(true), dto = phase1aDocument()
    delete dto.document.metadata.fabric_config
    await open(dto); manufacture()
    const retry = await screen.findByRole('button', { name: '重试3D预览' })
    expect(screen.getAllByText(/测试站正在处理另一项三维任务/)).toHaveLength(1)
    const before = backend.evaluated.at(-1)!
    const count = backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview')).length
    expect(retry).toBeEnabled()
    act(() => { retry.click(); retry.click() })
    await screen.findByLabelText('测试共享 Fabric 画面')
    expect(backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview'))).toHaveLength(count + 1)
    expect(backend.evaluated.at(-1)).toBe(before)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '重试3D预览' })).not.toBeInTheDocument()
  })
  it('R1 can open and edit B while A manufactures without showing A results or releasing its compute guard', async () => {
    const backend = startBackend(); await open(); manufacture()
    await screen.findByLabelText('测试共享 Fabric 画面')
    const old = backend.evaluated.at(-1)!
    fireEvent.click(screen.getByRole('button', { name: '生成最终模型' }))
    expect(backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fusion'))).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    const next = phase1aDocument()
    next.document.elements[0].x = 45
    const raw = JSON.stringify(next.document), file = new File([raw], 'work-b.pattern.json', { type: 'application/json' })
    Object.defineProperty(file, 'text', { value: async () => raw })
    fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'), { target: { files: [file] } })
    await waitFor(() => expect(backend.evaluated.at(-1)!.document_id).not.toBe(old.document_id))
    const b = backend.evaluated.at(-1)!
    expect(screen.queryByLabelText('测试共享 Fabric 画面')).not.toBeInTheDocument()
    expect(drafts.save).toHaveBeenCalled()
    manufacture()
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    heightSettings()
    fireEvent.change(screen.getByLabelText('高度变化'), { target: { value: 'directional' } })
    await waitFor(() => expect(backend.evaluated.at(-1)!.document_revision).toBe(b.document_revision + 1))
    expect(backend.evaluated.at(-1)!.document_id).toBe(b.document_id)
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    expect(screen.queryByLabelText('测试共享 Fabric 画面')).not.toBeInTheDocument()
    expect(backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview'))).toHaveLength(1)
    await act(async () => backend.finish(reply({ code: 'staging_busy', message: 'old A response' }, 429)))
    await screen.findByLabelText('测试共享 Fabric 画面')
    expect(screen.queryByText(/old A response/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeEnabled()
    const previews = backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview'))
    expect(previews).toHaveLength(2)
    expect(JSON.parse(String(previews[1][1]?.body)).document.document_id).toBe(b.document_id)
  })
  it('B2 manufacture groups switch only display state, retain one form, and leave requests/history unchanged', async () => {
    const backend = startBackend(); const view = await open(); manufacture()
    await screen.findByLabelText('测试共享 Fabric 画面')
    const input = screen.getByRole('slider', { name: '单元大小滑杆' })
    const picture = screen.getByLabelText('测试共享 Fabric 画面')
    const count = backend.fetcher.mock.calls.length
    const official = backend.evaluated.at(-1)!
    for (const title of ['高度与变化', '基底与输出模式', '预览与最终制造', '形状与单元']) {
      expandSection(title)
      expect(screen.getByRole('button', { name: title })).toHaveAttribute('aria-expanded', 'true')
      expect(view.container.querySelectorAll('.manufacturing-panel')).toHaveLength(1)
    }
    expect(screen.getByRole('slider', { name: '单元大小滑杆' })).toBe(input)
    expect(screen.getByLabelText('测试共享 Fabric 画面')).toBe(picture)
    expect(backend.fetcher.mock.calls).toHaveLength(count)
    expect(backend.evaluated.at(-1)).toBe(official)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '高度与变化' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: '基底与输出模式' })).toHaveAttribute('aria-expanded', 'false')
    const actions = view.container.querySelector<HTMLElement>('.manufacturing-action-dock')!
    expect(actions).toContainElement(screen.getByRole('button', { name: '生成最终模型' }))
    expect(view.container.querySelector('.function-panel-scroll')).not.toContainElement(actions)
  })
  it('center recipe protects a failed save, commits once, and Reset/Undo preserve the original shape', async () => {
    const backend = startBackend(), dto = phase1aDocument()
    delete dto.document.metadata.fabric_config
    await open(dto); manufacture(); await screen.findByLabelText('测试共享 Fabric 画面')
    const before = backend.evaluated.at(-1)!
    heightSettings(true)
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: 'center-height' } })
    drafts.save.mockRejectedValueOnce(new Error('disk unavailable'))
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByText(/当前作品保存失败，已取消切换/)
    expect(backend.evaluated.at(-1)).toBe(before)
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByRole('button', { name: '恢复中心隆起配方' })
    const first = backend.evaluated.at(-1)!
    expect(first.document_revision).toBe(before.document_revision + 1)
    expect(first.document.fields).toHaveLength(1)
    expect(screen.getByLabelText('高度变化')).toHaveValue('center')
    expect(screen.getByLabelText('Unit Cell 类型')).toHaveValue('original')
    const controls = within(screen.getByRole('region', { name: '直接高度控制' }))
    const slider = controls.getByRole('slider', { name: '影响范围滑杆' }), requests = backend.evaluated.length
    fireEvent.change(slider, { target: { value: '20' } })
    expect(backend.evaluated).toHaveLength(requests)
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(backend.evaluated).toHaveLength(requests + 1))
    const edited = backend.evaluated.at(-1)!
    expect((edited.document.fields[0].parameters as any).ring_width).toBe(40)
    fireEvent.click(screen.getByRole('button', { name: '恢复中心隆起配方' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(first.document))
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(edited.document))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(first.document))
    expect(backend.fetcher.mock.calls.some(([url]) => String(url).endsWith('/fusion'))).toBe(false)
  })
  it('default original source can explicitly bind an existing advanced height field without choosing a unit or creating a field', async () => {
    const backend=startBackend(),dto=phase1aDocument();delete dto.document.metadata.fabric_config
    dto.document.fields=[{id:'existing-user-field',type:'linear',parameters:{angle:0,start:10,end:70}}]
    await open(dto);manufacture();await screen.findByLabelText('测试共享 Fabric 画面')
    const before=backend.evaluated.at(-1)!
    heightSettings()
    fireEvent.click(screen.getByText('高级参数场绑定',{exact:true}))
    fireEvent.click(within(screen.getByRole('region',{name:'Fabric 测试'})).getByRole('checkbox'))
    await waitFor(()=>expect(backend.evaluated.at(-1)!.document_revision).toBe(before.document_revision+1))
    expect(backend.evaluated.at(-1)!.document.fields).toEqual(before.document.fields)
    expect(backend.evaluated.at(-1)!.document.metadata.fabric_config).toMatchObject({shape_source:'original',
      field_modifiers:{height:{enabled:true,field_id:'existing-user-field'}}})
    expect((backend.evaluated.at(-1)!.document.metadata.fabric_config as any).unit_cell).toBeUndefined()
  })
  it('empty original source gives an import/add guide and never requests a fake preview', async () => {
    const backend=startBackend(),dto=phase1aDocument();delete dto.document.metadata.fabric_config;dto.document.elements=[];dto.document.transforms={}
    render(<App/>);await screen.findByText('Backend Online')
    const raw=JSON.stringify(dto.document),file=new File([raw],'empty.pattern.json',{type:'application/json'})
    Object.defineProperty(file,'text',{value:async()=>raw})
    fireEvent.change(screen.getByLabelText('选择 PatternDocument 项目文件'),{target:{files:[file]}})
    await waitFor(()=>expect(backend.evaluated).toHaveLength(1));manufacture()
    await screen.findByText('当前没有可挤出的原图。请导入图案或在设计中添加图形。')
    expect(backend.fetcher.mock.calls.some(([url])=>String(url).endsWith('/fabric/preview'))).toBe(false)
    expect(screen.queryByLabelText('测试共享 Fabric 画面')).toBeNull()
  })
  it('absent Fabric config displays a default original candidate without a commit, and a height effect commits once without choosing a cell', async () => {
    const backend=startBackend(),dto=phase1aDocument();delete dto.document.metadata.fabric_config
    await open(dto);manufacture();await screen.findByLabelText('测试共享 Fabric 画面')
    expect(backend.evaluated.at(-1)!.document.metadata.fabric_config).toBeUndefined()
    expect(screen.getByRole('button',{name:'撤销'})).toBeDisabled()
    expect(screen.getByLabelText('Unit Cell 类型')).toHaveValue('original')
    const before=backend.evaluated.at(-1)!
    heightSettings()
    fireEvent.change(screen.getByLabelText('高度变化'),{target:{value:'wave'}})
    await waitFor(()=>expect(backend.evaluated.at(-1)!.document_revision).toBe(before.document_revision+1))
    expect(backend.evaluated.at(-1)!.document.metadata.fabric_config).toMatchObject({shape_source:'original',original_shape:{height_mm:2}})
    expect((backend.evaluated.at(-1)!.document.metadata.fabric_config as any).unit_cell).toBeUndefined()
    expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(1)
    fireEvent.click(screen.getByRole('button',{name:'撤销'}))
    await waitFor(()=>expect(backend.evaluated.at(-1)!.document.metadata.fabric_config).toBeUndefined())
    expect(backend.fetcher.mock.calls.some(([url])=>String(url).endsWith('/fusion'))).toBe(false)
  })
  it('does not discard or apply an unapplied 2D shortcut when switching to wave recipes', async () => {
    const backend = startBackend(); await open()
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const minimum = screen.getByLabelText('最小尺寸比例')
    fireEvent.change(minimum, { target: { value: '.8' } }); fireEvent.blur(minimum)
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    manufacture()
    heightSettings(true)
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: 'wave-height' } })
    const count = backend.evaluated.length
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByText('二维尺寸效果尚未应用，请返回设计先应用或取消，再应用 Fabric 配方。')
    expect(backend.evaluated).toHaveLength(count)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    expect(screen.getByLabelText('最小尺寸比例')).toHaveValue(.8)
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
  })
  it('wave recipe protects draft, commits once, waits for slider release and resets with Undo/Redo', async () => {
    const backend = startBackend(); await open(); manufacture()
    expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(0)
    heightSettings(true)
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: 'wave-height' } })
    expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(0)
    drafts.save.mockRejectedValueOnce(new Error('disk unavailable'))
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByText(/当前作品保存失败，已取消切换/)
    const before = backend.evaluated.at(-1)!
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByRole('button', { name: '恢复波浪起伏配方' })
    const first = backend.evaluated.at(-1)!
    expect(first.document_revision).toBe(before.document_revision + 1)
    expect(first.document.fields).toHaveLength(1)
    expect(screen.getByLabelText('高度变化')).toHaveValue('wave')
    expect(screen.getByLabelText('Fabric 预设')).toHaveValue('wave-height')
    const controls = within(screen.getByRole('region', { name: '直接高度控制' }))
    const slider = controls.getByRole('slider', { name: 'wavelength滑杆' }), requests = backend.evaluated.length
    fireEvent.change(slider, { target: { value: '90' } })
    expect(backend.evaluated).toHaveLength(requests)
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(backend.evaluated).toHaveLength(requests + 1))
    const edited = backend.evaluated.at(-1)!
    expect((edited.document.fields[0].parameters as any).wavelength).toBe(90)
    fireEvent.click(screen.getByRole('button', { name: '恢复波浪起伏配方' }))
    await waitFor(() => expect((backend.evaluated.at(-1)!.document.fields[0].parameters as any).wavelength).toBe(36))
    const reset = backend.evaluated.at(-1)!
    expect(reset.document).toEqual(first.document)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(edited.document))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(reset.document))
    expect(backend.fetcher.mock.calls.some(([url]) => String(url).endsWith('/fusion'))).toBe(false)
  })
  it('explicit original shape replaces the source, keeps a preview and restores the cell through Undo without manufacturing', async () => {
    const backend = startBackend(); await open(); manufacture()
    await screen.findByLabelText('测试共享 Fabric 画面')
    const before = backend.evaluated.at(-1)!
    fireEvent.change(screen.getByLabelText('Unit Cell 类型'), { target: { value: 'original' } })
    await waitFor(() => expect(backend.evaluated.at(-1)!.document_revision).toBe(before.document_revision + 1))
    await waitFor(() => expect(screen.getByLabelText('测试共享 Fabric 画面')).toHaveTextContent('60 / 2'))
    expect(screen.getByLabelText('Unit Cell 类型')).toHaveValue('original')
    expect(backend.evaluated.at(-1)!.document.metadata.fabric_config).toMatchObject({shape_source:'original',unit_cell:{type:'pyramid'}})
    fireEvent.click(screen.getByRole('button', {name: '撤销'}))
    await screen.findByLabelText('测试共享 Fabric 画面')
    expect(screen.getByLabelText('Unit Cell 类型')).toHaveValue('pyramid')
    expect(backend.fetcher.mock.calls.some(([url]) => String(url).endsWith('/fusion'))).toBe(false)
  })
  it('moves one form to the inspector, displays drag drafts without requests and commits once on release', async () => {
    const backend = startBackend(); await open(); manufacture()
    const picture = await screen.findByLabelText('测试共享 Fabric 画面')
    expect(within(screen.getByRole('main')).queryByRole('region', { name: '制造检查' })).toBeNull()
    expect(within(screen.getByRole('complementary', { name: '功能与参数面板' })).getAllByRole('region', { name: '制造检查' })).toHaveLength(1)
    const original = backend.evaluated.at(-1)!
    const calls = () => backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview')).length
    const before = calls(), evaluations = backend.evaluated.length
    const size = screen.getByRole('slider', { name: '单元大小滑杆' })
    fireEvent.change(size, { target: { value: '5' } })
    expect(picture).toHaveTextContent('5 / 3')
    expect(calls()).toBe(before); expect(backend.evaluated).toHaveLength(evaluations)
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '收起功能面板' }))
    fireEvent.click(screen.getByRole('button', { name: '功能与参数' }))
    expect(screen.getByRole('slider', { name: '单元大小滑杆' })).toBe(size)
    expect(screen.getByLabelText('测试共享 Fabric 画面')).toBe(picture)
    expect(picture).toHaveTextContent('5 / 3')
    expect(calls()).toBe(before); expect(backend.evaluated).toHaveLength(evaluations)
    fireEvent.pointerUp(size)
    await waitFor(() => expect(calls()).toBe(before + 1))
    expect(backend.evaluated).toHaveLength(evaluations + 1)
    expect(backend.evaluated.at(-1)!.document_revision).toBe(original.document_revision + 1)
    expect(backend.evaluated.at(-1)!.document.elements).toEqual(original.document.elements)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(picture).toHaveTextContent('2 / 3'))
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    expect(screen.getByLabelText('测试共享 Fabric 画面')).toBe(picture)
    manufacture(); expect(screen.getByLabelText('测试共享 Fabric 画面')).toBe(picture)
  })
  it('height/preset/reset are single history entries and a failed draft save does not replace work', async () => {
    const backend = startBackend(); await open(); manufacture()
    expect(screen.getByLabelText('高度变化')).toHaveValue('uniform')
    expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(0)
    heightSettings()
    fireEvent.change(screen.getByLabelText('高度变化'), { target: { value: 'directional' } })
    await waitFor(() => expect(backend.evaluated).toHaveLength(2))
    const first = backend.evaluated.at(-1)!
    expect(first.document_revision).toBe(1); expect(first.document.fields).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(0))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(1))
    heightSettings(true)
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: 'direction-gradient' } })
    drafts.save.mockRejectedValueOnce(new Error('disk unavailable'))
    const before = backend.evaluated.at(-1)!
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByText(/当前作品保存失败，已取消切换/)
    expect(backend.evaluated.at(-1)).toBe(before)
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByRole('button', { name: '恢复方向渐变配方' })
    const recipe = backend.evaluated.at(-1)!
    expect(recipe.document_revision).toBe(before.document_revision + 1)
    const controls = within(screen.getByRole('region', { name: '直接高度控制' }))
    const angle = controls.getByLabelText('angle')
    const requestCount = backend.evaluated.length
    const slider = controls.getByRole('slider', { name: 'angle滑杆' })
    fireEvent.change(slider, { target: { value: '45' } })
    expect(backend.evaluated).toHaveLength(requestCount)
    fireEvent.pointerUp(slider)
    await waitFor(() => expect(backend.evaluated).toHaveLength(requestCount + 1))
    const minHeight = controls.getByRole('spinbutton', { name: 'min_height_mm' })
    fireEvent.change(minHeight, { target: { value: '100' } }); fireEvent.blur(minHeight)
    await screen.findByText('最低高度不能大于最高高度。')
    expect(minHeight).toHaveValue(2)
    fireEvent.change(angle, { target: { value: '90' } }); fireEvent.blur(angle)
    await waitFor(() => expect((backend.evaluated.at(-1)!.document.fields[0].parameters as any).angle).toBe(90))
    const modified = backend.evaluated.at(-1)!
    fireEvent.click(screen.getByRole('button', { name: '恢复方向渐变配方' }))
    await waitFor(() => expect((backend.evaluated.at(-1)!.document.fields[0].parameters as any).angle).toBe(0))
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document).toEqual(modified.document))
  })
  it('cannot bypass a draining fusion by duplicate click, mode switch, design edit or preflight', async () => {
    const backend = startBackend(); await open(); manufacture()
    const button = screen.getByRole('button', { name: '生成最终模型' })
    act(() => { button.click(); button.click() })
    expect(backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fusion'))).toHaveLength(1)
    expect(screen.getByRole('button', { name: '检查可制造性' })).toBeDisabled()
    heightSettings()
    fireEvent.change(screen.getByLabelText('高度变化'), { target: { value: 'directional' } })
    await waitFor(() => expect(backend.evaluated).toHaveLength(2))
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    manufacture()
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    expandSection('预览与最终制造')
    expect(screen.getByRole('button', { name: '更新3D预览' })).toBeDisabled()
    await act(async () => backend.finish(reply({ code: 'staging_busy', message: 'another user is computing' }, 429)))
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeEnabled()
    expect(screen.queryByText(/another user/)).toBeNull() // discarded old document response
  })
  it.each(['direction-gradient', 'wave-height', 'center-height'])('preserves pending Layout across %s and later Apply does not erase the recipe', async preset => {
    const backend = startBackend()
    const dto = createExampleDocument('basic-grid', 'test')
    dto.document.metadata.fabric_config = phase1aDocument().document.metadata.fabric_config
    await open(dto)
    const rows = screen.getByLabelText('行数')
    fireEvent.change(rows, { target: { value: '5' } }); fireEvent.blur(rows)
    manufacture()
    heightSettings(true)
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: preset } })
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByRole('button', { name: preset === 'wave-height' ? '恢复波浪起伏配方' : preset === 'center-height' ? '恢复中心隆起配方' : '恢复方向渐变配方' })
    const applied = backend.evaluated.at(-1)!
    expect((applied.document.metadata['xiaomang_pattern_lab.parametric'] as any).grid.rows).toBe(3)
    expect(screen.getByLabelText('行数')).toHaveValue(5)
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    fireEvent.click(screen.getByRole('button', { name: '应用布局' }))
    await waitFor(() => expect((backend.evaluated.at(-1)!.document.metadata['xiaomang_pattern_lab.parametric'] as any).grid.rows).toBe(5))
    expect(backend.evaluated.at(-1)!.document.metadata.web_fabric_recipe).toEqual(applied.document.metadata.web_fabric_recipe)
    expect(backend.evaluated.at(-1)!.document.fields).toEqual(applied.document.fields)
  })
})
