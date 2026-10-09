import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { phase1aBounds, phase1aCatalog, phase1aDocument } from './test/phase1aFixture'
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
function startBackend() {
  const evaluated: PatternDocumentDTO[] = []
  let finish!: (response: Response) => void
  const catalog = structuredClone(phase1aCatalog)
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
      const dto = body.document, cell = dto.document.metadata.fabric_config.unit_cell
      return reply({ schema_version: '1.0', kind: 'fabric_instance_preview', document_id: dto.document_id,
        document_revision: dto.document_revision, preview_id: `p-${dto.document_revision}`,
        placement_mode: 'pattern_points', unit_size_mode: cell.size_mode, element_count: 1,
        count: 1, active_count: 1, total_count: 1, skipped_count: 0, unmatched_reference_count: 0,
        preview_simplified: false, prototype: null, cache_hit: false,
        base_preview: { type: 'solid', bounds_mm: [10, 20, 70, 80], thickness_mm: .6 },
        timings_ms: { evaluate: 1, plan_and_prototype: 1, serialization: 1 }, instances: [{
          id: 'cell', source_id: 'square', final_geometry_id: 'square', x_mm: 40, y_mm: 50, z_mm: .6,
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
const manufacture = () => fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))

describe('Phase 1A real editor connections', () => {
  it('moves one form to the inspector, displays drag drafts without requests and commits once on release', async () => {
    const backend = startBackend(); await open(); manufacture()
    const picture = await screen.findByLabelText('测试共享 Fabric 画面')
    expect(within(screen.getByRole('main')).queryByRole('region', { name: '制造检查' })).toBeNull()
    expect(within(screen.getByRole('complementary', { name: '右侧检查器' })).getAllByRole('region', { name: '制造检查' })).toHaveLength(1)
    const original = backend.evaluated.at(-1)!
    const calls = () => backend.fetcher.mock.calls.filter(([url]) => String(url).endsWith('/fabric/preview')).length
    const before = calls(), evaluations = backend.evaluated.length
    const size = screen.getByRole('slider', { name: '单元大小滑杆' })
    fireEvent.change(size, { target: { value: '5' } })
    expect(picture).toHaveTextContent('5 / 3')
    expect(calls()).toBe(before); expect(backend.evaluated).toHaveLength(evaluations)
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
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
    fireEvent.change(screen.getByLabelText('高度变化'), { target: { value: 'directional' } })
    await waitFor(() => expect(backend.evaluated).toHaveLength(2))
    const first = backend.evaluated.at(-1)!
    expect(first.document_revision).toBe(1); expect(first.document.fields).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '撤销' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(0))
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    await waitFor(() => expect(backend.evaluated.at(-1)!.document.fields).toHaveLength(1))
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
    const minHeight = controls.getByLabelText('min_height_mm')
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
    fireEvent.change(screen.getByLabelText('高度变化'), { target: { value: 'directional' } })
    await waitFor(() => expect(backend.evaluated).toHaveLength(2))
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    manufacture()
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '更新3D预览' })).toBeDisabled()
    await act(async () => backend.finish(reply({ code: 'staging_busy', message: 'another user is computing' }, 429)))
    expect(screen.getByRole('button', { name: '生成最终模型' })).toBeEnabled()
    expect(screen.queryByText(/another user/)).toBeNull() // discarded old document response
  })
  it('preserves pending Layout across a recipe and later Apply does not erase the recipe', async () => {
    const backend = startBackend()
    const dto = createExampleDocument('basic-grid', 'test')
    dto.document.metadata.fabric_config = phase1aDocument().document.metadata.fabric_config
    await open(dto)
    const rows = screen.getByLabelText('行数')
    fireEvent.change(rows, { target: { value: '5' } }); fireEvent.blur(rows)
    manufacture()
    fireEvent.change(screen.getByLabelText('Fabric 预设'), { target: { value: 'direction-gradient' } })
    fireEvent.click(screen.getByRole('button', { name: '应用预设' }))
    await screen.findByRole('button', { name: '恢复方向渐变配方' })
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
