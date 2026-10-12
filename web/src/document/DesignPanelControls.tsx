import { ParameterPanel } from './ParameterPanel'
import { groupFor, type ParameterCatalog, type ParameterGroup, type ParameterValue } from './parameterSchema'
import { designValues, gridValues, newInfluence, physicalGroup } from './designControls'
import type { LinearSizeDraft } from './linearSize'
import { millimetresPerUnit } from '../model/project'

export interface DesignDisplay { unit: 'mm' | 'cm' | 'px'; grid: boolean; pngWidth: number }
export const defaultDesignDisplay: DesignDisplay = { unit: 'mm', grid: false, pngWidth: 1600 }
export function DesignPanelControls({ draft, catalog, onChange, display, onDisplay, areaOnly = false }: {
  draft: LinearSizeDraft; catalog: ParameterCatalog | null; onChange: (draft: LinearSizeDraft) => void;
  display: DesignDisplay; onDisplay: (display: DesignDisplay) => void; areaOnly?: boolean
}) {
  const values = draft.designValues ?? designValues(draft.source, catalog)
  const grid = draft.gridValues ?? gridValues(draft.source)
  const mm = millimetresPerUnit(draft.source.document) ?? 1
  const areas = draft.influenceAreas ?? [], selected = areas.find(a => a.id === draft.selectedArea) ?? areas[0]
  const group = selected ? physicalGroup(groupFor(catalog, 'design', selected.type), mm) : null
  const setValue = (key: string, value: ParameterValue) => onChange({ ...draft, designValues: { ...values, [key]: value } })
  const gridGroup = physicalGroup(groupFor(catalog, 'layout', 'grid'), mm)
  const arrangement: ParameterGroup | null = gridGroup && grid ? { label: '排列密度与间距', parameters: [
    ...gridGroup.parameters.filter(p => ['rows', 'columns', 'spacing_x', 'spacing_y'].includes(p.id)),
    { ...gridGroup.parameters.find(p => p.id === 'spacing_x')!, id: 'base_spacing', label: '基础间距' },
  ] } : null
  const board = draft.artboard ?? { width: draft.source.document.canvas.width * mm, height: draft.source.document.canvas.height * mm }
  const sourcePixels = ['px', 'pixel', 'pixels'].includes(draft.source.document.canvas.unit)
  const pixelMm = sourcePixels ? mm : 25.4 / 96
  const unitFactor = display.unit === 'cm' ? 10 : display.unit === 'px' ? pixelMm : 1
  return <>
    {!areaOnly && <>
      <details open><summary>排列</summary>
        <p className="inspector-readonly">密度＝行×列；基础间距同时设置横纵间距，单轴控件可随后覆盖。错列将奇数行沿横轴错开半格。仅对已选择并应用的Grid排列生效，不自动重排自由图案。</p>
        {arrangement && grid ? <>
          <p>{grid.rows * grid.columns} 个阵列位置</p>
          <ParameterPanel group={arrangement} values={grid} onCommit={(key, value) => {
            const next = key === 'base_spacing' ? { ...grid, base_spacing: Number(value), spacing_x: Number(value), spacing_y: Number(value) } : { ...grid, [key]: Number(value) }
            onChange({ ...draft, gridValues: next })
          }} />
          {groupFor(catalog, 'design', 'stagger') && <ParameterPanel group={groupFor(catalog, 'design', 'stagger')!} values={values} onCommit={setValue} />}
        </> : <p>当前保留导入图案的位置。需要规则排列时，先在左侧选择Grid并应用。</p>}
      </details>
      <details><summary>形状</summary>
        <p className="inspector-readonly">100%相对结构源的单元尺寸；宽扁比例保持面积，围绕原中心改变自身长宽。基础旋转为可撤销的附加角度；其他效果继续叠加。</p>
        {groupFor(catalog, 'design', 'shape') ? <ParameterPanel group={groupFor(catalog, 'design', 'shape')!} values={values} onCommit={setValue} /> : <p role="alert">后端图案控制Schema尚未加载。</p>}
      </details>
      <details><summary>随机</summary>
        <p className="inspector-readonly">尺寸随机为±比例，错位为各轴±mm。固定种子与元素ID保证刷新、预览和制造一致，不累加。</p>
        {groupFor(catalog, 'design', 'random') && <ParameterPanel group={physicalGroup(groupFor(catalog, 'design', 'random'), mm)!} values={values} onCommit={setValue} />}
        <button type="button" onClick={() => {
          const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647
          onChange({ ...draft, designValues: { ...values, seed, size_random: .2, position_jitter: .5,
            rotation_random: 20, size_percent: 90 + seed % 21, aspect: .85 + (seed % 31) / 100, rotation: seed % 31 - 15 } })
        }}>完整随机新方案</button><small>只改变本面板声明的形状/随机参数。预览后点击应用，一次Undo可恢复。</small>
      </details>
      <details><summary>画板与导出设置</summary>
        <label><input type="checkbox" checked={display.grid} onChange={e => onDisplay({ ...display, grid: e.target.checked })} />显示网格</label>
        <div className="field-picker"><label htmlFor="board-unit">显示单位</label><select id="board-unit" value={display.unit}
          onChange={e => onDisplay({ ...display, unit: e.target.value as DesignDisplay['unit'] })}>
          <option value="mm">mm</option><option value="cm">cm</option><option value="px">px（文档单位）</option></select></div>
        <p className="inspector-readonly">1 px＝{pixelMm.toFixed(6)} mm，{sourcePixels ? '依据像素文档的mm_per_unit' : '非像素文档按明确的96 DPI表示（25.4/96 mm）'}；这里只转换表示，不改变物理几何。画板改变不拉伸、不裁剪或重排图案。导出按画板裁切，制造仍使用完整几何。</p>
        {(['width', 'height'] as const).map(key => <label key={key} className="field-picker">
          画板{key === 'width' ? '宽度' : '高度'}（{display.unit}）<input aria-label={`画板${key === 'width' ? '宽度' : '高度'}`} type="number" min={.01} max={10000 / unitFactor}
            step="any" value={Number((board[key] / unitFactor).toFixed(6))} onChange={e => onChange({ ...draft, artboard: { ...board, [key]: Number(e.target.value) * unitFactor } })} /></label>)}
        <label className="field-picker">PNG宽度（像素）<input aria-label="PNG宽度" type="number" min={64} max={8192} value={display.pngWidth}
          onChange={e => onDisplay({ ...display, pngWidth: Number(e.target.value) })} /></label>
        <p className="inspector-readonly">PNG高度按画板比例计算，透明背景。SVG/PNG均不包含参考底图、网格和控制柄。</p>
      </details>
    </>}
    {areaOnly && <>
      <p className="inspector-readonly">最多3个影响区；重叠取最大权重，不依赖顺序。区域外不改本层前的状态。直线/曲线按到有限轴的距离生效（圆头）；椭圆为填充区域，非Ring环带。</p>
      <div className="layout-inspector-actions">{(['line', 'ellipse', 'curve'] as const).map(type => <button key={type} type="button" disabled={areas.length >= 3 || !groupFor(catalog, 'design', type)} onClick={() => {
        const area = newInfluence(type, draft.bounds, catalog, areas)
        onChange({ ...draft, influenceAreas: [...areas, area], selectedArea: area.id })
      }}>添加{type === 'line' ? '直线轴' : type === 'ellipse' ? '椭圆轴' : '曲线轴'}</button>)}</div>
      <div className="field-picker"><label htmlFor="influence-selected">当前影响区</label><select id="influence-selected" value={selected?.id ?? ''} onChange={e => onChange({ ...draft, selectedArea: e.target.value })}>
        {!areas.length && <option value="">请添加影响区（当前本层不生效）</option>}
        {areas.map(a => <option key={a.id} value={a.id}>{a.id} · {groupFor(catalog, 'design', a.type)?.label}{a.enabled ? '' : ' · 已停用'}</option>)}
      </select></div>
      {selected && group && <>
        <label><input type="checkbox" checked={selected.enabled} onChange={e => onChange({ ...draft, influenceAreas: areas.map(a => a.id === selected.id ? { ...a, enabled: e.target.checked } : a) })} />启用当前影响区</label>
        <ParameterPanel group={group} values={selected.parameters} onCommit={(key, value) => onChange({ ...draft, influenceAreas: areas.map(a => a.id === selected.id ? { ...a, parameters: { ...a.parameters, [key]: Number(value) } } : a) })} />
        <button type="button" onClick={() => onChange({ ...draft, influenceAreas: areas.filter(a => a.id !== selected.id), selectedArea: undefined })}>删除当前影响区</button>
        {selected.type === 'curve' && <small>二次Bezier路径：起点、一个控制点、终点。Python距离采用128段固定采样，控制点可在画布拖动。</small>}
      </>}
    </>}
  </>
}
