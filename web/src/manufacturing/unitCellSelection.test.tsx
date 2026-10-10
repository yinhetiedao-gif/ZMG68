import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { ManufacturingPanel } from './ManufacturingPanel'
import { phase1aCatalog, phase1aDocument } from '../test/phase1aFixture'
import { fabricUnitCell, setFabricUnitCellType, unitCellChoices } from '../document/fabricCell'

function catalog() {
  const result = structuredClone(phase1aCatalog)
  for (const { type } of unitCellChoices) result.definitions.fabric_cell![type] = structuredClone(result.definitions.fabric_cell!.pyramid)
  return result
}
const noop = () => undefined
function props(): ComponentProps<typeof ManufacturingPanel> {
  return { document: phase1aDocument(), parameterCatalog: catalog(), heightText: '2', onHeightChange: noop,
    validHeight: true, canBuild: true, onBuild: vi.fn(), status: 'idle', result: null, error: null,
    projectName: 'test', projectWarnings: [], isCurrentResult: () => false, onPreview: noop,
    onFabricType: noop, onFabricParameter: noop, onUnitCellType: vi.fn(), onUnitCellParameter: noop,
    onPlacementMode: noop, onFabricModifierEnabled: noop, onFabricModifierField: noop, onFabricModifierParameter: noop,
    onFabricPreset: noop, fabricPreviewStatus: 'idle', fabricPreviewResult: null, fabricPreviewError: null,
    onUpdateFabricPreview: vi.fn(), onRetryParameters: vi.fn() }
}
describe('Unit Cell parameter load and one authoritative selection', () => {
  it('distinguishes loading, request failure with retry and a successful retry', () => {
    const p = props(), ui = render(<ManufacturingPanel {...p} parameterCatalog={null} parameterLoad={{status: 'loading'}} />)
    expect(screen.getByText('正在加载单元参数…')).toBeVisible()
    expect(screen.getByLabelText('Unit Cell 类型')).toBeDisabled()
    ui.rerender(<ManufacturingPanel {...p} parameterCatalog={null} parameterLoad={{status: 'error', error: 'HTTP 503'}} />)
    expect(screen.getByText('HTTP 503')).toBeVisible()
    fireEvent.click(screen.getByRole('button', {name: '重试加载单元参数'}))
    expect(p.onRetryParameters).toHaveBeenCalledTimes(1)
    expect(p.onUnitCellType).not.toHaveBeenCalled()
    ui.rerender(<ManufacturingPanel {...p} parameterLoad={{status: 'ready'}} />)
    expect(screen.getByLabelText('Unit Cell 类型')).toBeEnabled()
    expect(screen.queryByText('HTTP 503')).toBeNull()
  })
  it('all eleven cards and dropdown options call the same handler, without manufacturing', () => {
    const p = props(); render(<ManufacturingPanel {...p} />)
    for (const {type, label} of unitCellChoices) {
      fireEvent.change(screen.getByLabelText('Unit Cell 类型'), {target: {value: type}})
      expect(p.onUnitCellType).toHaveBeenLastCalledWith(type)
      fireEvent.click(screen.getByRole('button', {name: `选择${label}`}))
      expect(p.onUnitCellType).toHaveBeenLastCalledWith(type)
    }
    expect(p.onUnitCellType).toHaveBeenCalledTimes(22)
    expect(p.onBuild).not.toHaveBeenCalled()
    expect(p.onUpdateFabricPreview).not.toHaveBeenCalled()
  })
  it('missing fin disables only fin, and a rejected edit retains the actual selected type', () => {
    const p = props(); delete p.parameterCatalog!.definitions.fabric_cell!.fin
    render(<ManufacturingPanel {...p} />)
    expect(screen.getByRole('button', {name: '选择鳍片'})).toBeDisabled()
    expect(screen.getByRole('button', {name: '选择圆顶'})).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Unit Cell 类型'), {target: {value: 'dome'}})
    expect(screen.getByLabelText('Unit Cell 类型')).toHaveValue('pyramid')
  })
  it('all eleven schema-driven changes preserve dimensions, mode, placement and other bindings in one revision', () => {
    const c = catalog(), original = phase1aDocument()
    const before = structuredClone(original.document.metadata.fabric_config) as Record<string, unknown>
    for (const {type} of unitCellChoices) {
      const next = setFabricUnitCellType(original, type, c)
      expect(next.document_revision).toBe(original.document_revision + (type === 'pyramid' ? 0 : 1))
      expect(fabricUnitCell(next)).toMatchObject({type, width_mm: 2, depth_mm: 2, height_mm: 3})
      const cfg = next.document.metadata.fabric_config as Record<string,unknown>
      for (const key of ['base','placement','field_modifiers','output_mode']) expect(cfg[key]).toEqual(before[key])
      expect(next.document.elements).toEqual(original.document.elements)
    }
  })
  it('does not require new placement defaults when retaining an existing placement; never fabricates missing definitions', () => {
    const c = catalog(), original = phase1aDocument()
    delete c.definitions.fabric_placement
    expect(fabricUnitCell(setFabricUnitCellType(original, 'fin', c))?.type).toBe('fin')
    expect(() => setFabricUnitCellType(original, 'fin', null)).toThrow(/未加载/)
    delete c.definitions.fabric_cell!.fin
    expect(() => setFabricUnitCellType(original, 'fin', c)).toThrow(/fin/)
    const noPlacement = structuredClone(original)
    delete (noPlacement.document.metadata.fabric_config as Record<string,unknown>).placement
    expect(() => setFabricUnitCellType(noPlacement, 'dome', c)).toThrow(/regular/)
  })
  it('rejects illegal retained dimensions without committing or mutating the original', () => {
    const c = catalog(), original = phase1aDocument(), before = JSON.stringify(original)
    c.definitions.fabric_cell!.fin.parameters.find(p => p.id === 'width_mm')!.max = 1
    expect(() => setFabricUnitCellType(original, 'fin', c)).toThrow(/width_mm/)
    expect(JSON.stringify(original)).toBe(before)
  })
  it('an old five-cell catalog disables the absent six, then a complete reload enables them without document edits', () => {
    const p = props(), old = catalog()
    for (const type of ['dome','frustum','hex_prism','wedge','cross','ring']) delete old.definitions.fabric_cell![type]
    const ui = render(<ManufacturingPanel {...p} parameterCatalog={old} />)
    for (const {type, label} of unitCellChoices) {
      const missing = !old.definitions.fabric_cell![type]
      expect((screen.getByRole('option', { name: new RegExp(` · ${type}(?:$|（)`) }) as HTMLOptionElement).disabled).toBe(missing)
      if (missing) expect(screen.getByRole('button', {name: `选择${label}`})).toBeDisabled()
    }
    ui.rerender(<ManufacturingPanel {...p} parameterCatalog={catalog()} />)
    for (const {label} of unitCellChoices) expect(screen.getByRole('button', {name: `选择${label}`})).toBeEnabled()
    expect(p.onUnitCellType).not.toHaveBeenCalled()
  })
  it('no cell has an explicit placement empty state and cannot claim an old preview is ready', () => {
    const p = props()
    p.document = setFabricUnitCellType(p.document!, 'none', p.parameterCatalog)
    render(<ManufacturingPanel {...p} fabricPreviewStatus="ready" />)
    const area = within(screen.getByRole('region', {name: '单元布点设置'}))
    expect(area.getByText('请先选择形状；暂无可编辑的布点参数。')).toBeVisible()
    expect(screen.queryByText('设计预览已就绪')).toBeNull()
    expect(screen.getByRole('button', {name: '生成最终制造网格'})).toBeDisabled()
  })
  it('valid cells retain the placement selector; missing definitions explain unavailable controls', () => {
    const p = props(), c = catalog()
    ;(p.document!.document.metadata.fabric_config as {placement: {mode: string}}).placement.mode = 'area_fill'
    delete c.definitions.fabric_placement
    const ui = render(<ManufacturingPanel {...p} parameterCatalog={c} />)
    expect(screen.getByLabelText('布点方式')).toBeEnabled()
    expect(screen.getByText(/后端未提供 regular 布点参数定义/)).toBeVisible()
    ui.rerender(<ManufacturingPanel {...p} parameterCatalog={null} parameterLoad={{status: 'error', error: 'HTTP 503'}} />)
    expect(screen.getByText('布点参数加载失败：HTTP 503')).toBeVisible()
  })
})
