import { useEffect, useState } from 'react'
import type { ManufacturingBuildResult } from '../api/manufacturing'
import type { ManufacturingStatus } from './useManufacturing'
import { StlExportButton } from './StlExportButton'
import { ParameterPanel } from '../document/ParameterPanel'
import { fabricBase, type FabricBaseType } from '../document/fabricBase'
import { fabricUnitCell, fabricPlacement, type UnitCellType } from '../document/fabricCell'
import { availableFabricFields, fabricFieldModifier, fabricModifierTypes, type FabricModifierType } from '../document/fabricModifiers'
import { groupFor, type ParameterCatalog, type ParameterValue } from '../document/parameterSchema'
import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { FabricPreflightPanel } from './FabricPreflightPanel'
import { FabricFusionPanel } from './FabricFusionPanel'
import { fabricPresets } from '../document/fabricPresets'
import { fabricDesignWarnings, fabricPreviewSummary } from '../document/fabricDesignSummary'
import { FABRIC_PREVIEW_NOTICE, fabricExportNotice } from './fabricCopy'
import { formatMm } from '../model/formatMm'
import { RealSizePanel } from './RealSizePanel'

interface Props {
  heightText: string
  onHeightChange: (value: string) => void
  validHeight: boolean
  canBuild: boolean
  onBuild: () => void
  status: ManufacturingStatus
  result: ManufacturingBuildResult | null
  error: string | null
  projectName: string | null
  projectWarnings: string[]
  isCurrentResult: (resultId: string) => boolean
  onPreview: () => void
  onBackDesign?: () => void
  document: PatternDocumentDTO | null
  designBounds?: BoundsMM | null
  canEditSize?: boolean
  onConfirmRealSize?: (widthMm: number, heightMm: number) => void
  parameterCatalog: ParameterCatalog | null
  onFabricType: (type: FabricBaseType | 'none') => void
  onFabricParameter: (key: string, value: ParameterValue) => void
  onUnitCellType: (type: UnitCellType | 'none') => void
  onUnitCellParameter: (section: 'cell' | 'placement', key: string, value: ParameterValue) => void
  onPlacementMode: (mode: 'area_fill' | 'pattern_points') => void
  onFabricModifierEnabled: (type: FabricModifierType, enabled: boolean) => void
  onFabricModifierField: (type: FabricModifierType, fieldId: string) => void
  onFabricModifierParameter: (type: FabricModifierType, key: string, value: ParameterValue) => void
  onFabricPreset: (presetId: string) => void
  fabricPreviewStatus: 'idle' | 'building' | 'ready' | 'error' | 'stale'
  fabricPreviewResult: FabricDesignPreview | null
  fabricPreviewError: string | null
  onUpdateFabricPreview: () => void
  candidateFetcher?: typeof fetch
  fabricStlTestExportEnabled?: boolean
}

const labels: Record<ManufacturingStatus, string> = {
  idle: '尚未生成', building: '正在检查并生成…', ready: '模型已生成',
  warning: '模型已生成，存在提醒', error: '生成失败', stale: '结果已过期，请重新检查并生成',
}

export function ManufacturingPanel(props: Props) {
  const { result, status } = props
  const base = fabricBase(props.document)
  const fabricGroup = base && groupFor(props.parameterCatalog, 'fabric_base', base.type)
  const cell = fabricUnitCell(props.document)
  const placement = fabricPlacement(props.document)
  const cellGroup = cell && groupFor(props.parameterCatalog, 'fabric_cell', cell.type)
  const placementGroup = placement && groupFor(props.parameterCatalog, 'fabric_placement', 'regular')
  const fabricFields = availableFabricFields(props.document)
  const summary = fabricPreviewSummary(props.document,
    props.fabricPreviewStatus === 'ready' ? props.fabricPreviewResult : null)
  const designWarnings = fabricDesignWarnings(props.document)
  const [presetId, setPresetId] = useState(fabricPresets[0].id)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  useEffect(() => {
    if (status !== 'building') return
    const started = performance.now()
    setElapsedSeconds(0)
    const timer = window.setInterval(() => setElapsedSeconds((performance.now() - started) / 1000), 100)
    return () => window.clearInterval(timer)
  }, [status])
  const geometry = result?.geometry_validation_summary
  const mesh = result?.mesh_validation_summary
  const conversion = result?.conversion_summary
  const notes = result ? [
    ...(result.component_count > 1 ? [`${result.component_count} 个独立组件；请确认每个组件都能独立打印。`] : []),
    ...result.warnings,
    ...(conversion?.warnings ?? []),
    ...(geometry?.issues ?? []).map((issue) => issue.message ?? issue.code ?? '二维几何问题'),
    ...(mesh?.issues ?? []).map((issue) => issue.message ?? issue.code ?? '网格问题'),
  ] : []
  return <section className="manufacturing-panel" aria-label="制造检查">
    <div className="manufacturing-heading"><span className="eyebrow">{base ? 'FABRIC DESIGN PREVIEW' : 'FINAL MANUFACTURING MESH'}</span><h1>{base ? 'Fabric 设计预览' : '制造检查'}</h1>
      <p>{base ? '快速查看基底与单元布点；此预览不是可打印制造模型。' : '从当前二维设计生成最终制造网格；此操作不会更改设计或撤销历史。'}</p>
      <button type="button" className="workflow-back" onClick={props.onBackDesign}>返回设计</button></div>
    {props.document && <RealSizePanel document={props.document} bounds={props.designBounds ?? null}
      disabled={!props.canEditSize} onConfirm={(width, height) => props.onConfirmRealSize?.(width, height)} />}
    <section className="manufacturing-settings" aria-label="Fabric Base">
      {props.document && <section aria-label="Fabric Preset">
        <h2>Fabric 预设</h2>
        <label htmlFor="fabric-preset">Fabric 预设</label>
        <select id="fabric-preset" value={presetId} onChange={(event) => setPresetId(event.target.value)}>
          {fabricPresets.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
        </select>
        <button type="button" className="ui-secondary" onClick={() => props.onFabricPreset(presetId)}>应用预设</button>
      </section>}
      <label htmlFor="fabric-base-type">Fabric Base 类型</label>
      <select id="fabric-base-type" value={base?.type ?? 'none'} onChange={(event) =>
        props.onFabricType(event.target.value as FabricBaseType | 'none')}>
        <option value="none">标准二维挤出</option><option value="solid">Solid Base</option><option value="grid">Grid Base</option>
      </select>
      {base && <p>基底使用最终二维制造几何的外接矩形（mm）；Solid 会填满矩形，Grid 会生成贯通网孔，不沿原图轮廓或保留原图孔洞。</p>}
      {base && fabricGroup && <ParameterPanel group={fabricGroup} values={{ ...base }}
        onCommit={props.onFabricParameter} />}
      {base && <section aria-label="Fabric Unit Cell">
        <label htmlFor="fabric-cell-type">Unit Cell 类型</label>
        <select id="fabric-cell-type" value={cell?.type ?? 'none'} onChange={(event) =>
          props.onUnitCellType(event.target.value as UnitCellType | 'none')}>
          <option value="none">无单元</option><option value="cylinder">Cylinder 圆柱</option>
          <option value="cone">Cone 圆锥</option><option value="pyramid">Pyramid 方锥</option>
          <option value="double_tower">DoubleTower 双塔</option><option value="fin">Fin 鳍片</option>
        </select>
        {cell && cellGroup && <><h2>UNIT CELL SIZE</h2><ParameterPanel group={cellGroup}
          values={{ ...cell, size_mode: cell.size_mode ?? 'follow_pattern' }}
          onCommit={(key, value) => props.onUnitCellParameter('cell', key, value)} />
          <p>固定尺寸不继承二维大小；跟随图案按最终二维尺寸比例调整宽深。Fabric 比例场在两种模式下仍可叠加。</p>
        </>}
        {cell && placement && <><label htmlFor="fabric-placement-mode">布点方式</label>
          <select id="fabric-placement-mode" value={placement.mode ?? 'area_fill'}
            onChange={(event) => props.onPlacementMode(event.target.value as 'area_fill' | 'pattern_points')}>
            <option value="area_fill">全区域</option><option value="pattern_points">按图案元素</option>
          </select></>}
        {cell && placement && (placement.mode ?? 'area_fill') === 'area_fill' && placementGroup &&
          <ParameterPanel group={placementGroup} values={{ ...placement }}
            onCommit={(key, value) => props.onUnitCellParameter('placement', key, value)} />}
        {cell && (placement?.mode ?? 'area_fill') === 'pattern_points' && <p>图案元素：{props.fabricPreviewResult?.element_count ?? '待更新'} · 单元实例：{props.fabricPreviewResult?.total_count ?? '待更新'}</p>}
        {cell && <section aria-label="Fabric Field Modifiers">
          <h2>Fabric 参数场驱动</h2>
          <p>使用当前设计的 Shared Field 控制单元实例；此设置只影响 3D 设计预览。</p>
          {!fabricFields.length && <p>请先在设计界面添加参数场。</p>}
          {fabricModifierTypes.map((type) => {
            const modifierFields = availableFabricFields(props.document, type)
            const group = groupFor(props.parameterCatalog, 'fabric_modifier', type)
            const modifier = fabricFieldModifier(props.document, type)
            return <section key={type} aria-label={`Fabric ${group?.label ?? type}`}>
              <label><input type="checkbox" checked={modifier?.enabled === true}
                disabled={!modifier && (!group || !modifierFields.length)}
                onChange={(event) => props.onFabricModifierEnabled(type, event.target.checked)} />
                {group?.label ?? type}</label>
              {modifier?.enabled && <>
                <label htmlFor={`fabric-${type}-field`}>驱动参数场</label>
                <select id={`fabric-${type}-field`} value={modifier.field_id}
                  onChange={(event) => props.onFabricModifierField(type, event.target.value)}>
                  {modifierFields.map((field) => <option key={field.id} value={field.id}>{field.id} · {field.type}</option>)}
                </select>
                {group && <ParameterPanel group={{ ...group, parameters: group.parameters.filter((parameter) =>
                  type !== 'orientation' || parameter.id === 'direction_mode' || parameter.id === 'angle_offset_deg' ||
                  ((modifier.direction_mode ?? 'value') === 'gradient' ? parameter.id === 'alignment' : parameter.id !== 'alignment')) }}
                  values={{ ...Object.fromEntries(group.parameters.map((parameter) => [parameter.id, parameter.default])), ...modifier }}
                  onCommit={(key, value) => props.onFabricModifierParameter(type, key, value)} />}
              </>}
            </section>
          })}
        </section>}
        {cell && <p>{FABRIC_PREVIEW_NOTICE} {fabricExportNotice(props.fabricStlTestExportEnabled)}</p>}
      </section>}
    </section>
    <div className="manufacturing-settings">
      {!base && <><label htmlFor="manufacturing-height">厚度 <span>mm</span></label>
        <input id="manufacturing-height" type="number" min="0.01" step="0.1" value={props.heightText}
          onChange={(event) => props.onHeightChange(event.target.value)} /></>}
      <button type="button" className="ui-primary" onClick={base ? props.onUpdateFabricPreview : props.onBuild}
        disabled={!props.canBuild || (base ? props.fabricPreviewStatus === 'building' : status === 'building')}>
        {base ? '更新3D预览' : '检查并生成'}</button>
    </div>
    {base && props.document && <FabricPreflightPanel document={props.document}
      fetcher={props.candidateFetcher} disabled={!props.canBuild} />}
    {base && props.document && <FabricFusionPanel document={props.document}
      fetcher={props.candidateFetcher} disabled={!props.canBuild} testExportEnabled={props.fabricStlTestExportEnabled} />}
    {!props.validHeight && <p className="manufacturing-error" role="alert">厚度必须大于 0 mm。</p>}
    <div className={`manufacturing-status ${base ? props.fabricPreviewStatus : status}`} role="status">
      {base ? ({ idle: '尚未更新设计预览', building: '正在更新3D预览…', ready: '设计预览已就绪',
        stale: '设计已变化，请更新3D预览', error: '设计预览失败' }[props.fabricPreviewStatus]) : labels[status]}</div>
    {base && props.fabricPreviewError && <p className="manufacturing-error" role="alert">{props.fabricPreviewError}</p>}
    {base && props.fabricPreviewResult && <><p>可见单元：{props.fabricPreviewResult.active_count} / {props.fabricPreviewResult.total_count}</p>
      <details className="diagnostic-details"><summary>诊断详情</summary><p>
        Python evaluate {props.fabricPreviewResult.timings_ms.evaluate.toFixed(1)} ms ·
        plan {props.fabricPreviewResult.timings_ms.plan_and_prototype.toFixed(1)} ms
        {props.fabricPreviewResult.client_request_ms !== undefined ? ` · 请求往返 ${props.fabricPreviewResult.client_request_ms.toFixed(1)} ms` : ''}
        {props.fabricPreviewResult.cache_hit ? ' · 已复用预览缓存' : ''}
      </p></details></>}
    {base && props.fabricPreviewResult?.preview_simplified && <p role="note">预览已简化，最终设计参数未改变。</p>}
    {base && <section className="manufacturing-report" aria-label="Fabric Preview Summary">
      <h2>设计预览摘要</h2>
      <dl>
        <div><dt>Cell</dt><dd>{summary.cell}</dd></div>
        <div><dt>Instances</dt><dd>{summary.instances ?? '待更新'}</dd></div>
        <div><dt>Height</dt><dd>{summary.height}</dd></div>
        <div><dt>Scale</dt><dd>{summary.scale}</dd></div>
        <div><dt>Placement</dt><dd>{summary.placement}</dd></div>
        <div><dt>Preview</dt><dd>{summary.preview}</dd></div>
      </dl>
      {designWarnings.length > 0 && <div className="manufacturing-notes" role="note">
        <strong>设计提醒（不阻止预览）</strong><ul>{designWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      </div>}
    </section>}
    {!base && status === 'building' && <p className="manufacturing-progress">
      处理流程：二维几何检查 → 制造几何转换 → 3D 模型生成 → Mesh 检查 · 已用 {elapsedSeconds.toFixed(1)} 秒
    </p>}
    {!base && props.error && <p className="manufacturing-error" role="alert">{props.error}</p>}
    {!base && result && <div className="manufacturing-report">
      <dl>
        <div><dt>几何检查</dt><dd>{geometry?.error_count ? `${geometry.error_count} 个错误` : `有效 · ${geometry?.checked_count ?? 0} 个元素`}</dd></div>
        <div><dt>网格检查</dt><dd>{mesh?.is_watertight ? '封闭' : '未封闭'}{mesh ? ` · ${mesh.error_count} 个错误` : ''}</dd></div>
        <div><dt>独立组件</dt><dd>{result.component_count}</dd></div>
        <div><dt>成品尺寸 X / Y / Z</dt><dd>{result.bounds_mm
          ? `${formatMm(result.bounds_mm.size_x)} × ${formatMm(result.bounds_mm.size_y)} × ${formatMm(result.bounds_mm.size_z)} mm`
          : '未取得尺寸'}</dd></div>
      </dl>
      <details className="diagnostic-details"><summary>诊断详情</summary>
        <small className="manufacturing-result-id">结果编号：{result.manufacturing_result_id}</small>
        <p>连通性：{result.connectivity_summary.component_count} 个连通组件 · {result.connectivity_summary.isolated_count} 个孤立元素</p>
        <p>转换：{conversion?.converted_count ?? 0} / {conversion?.input_count ?? 0} 个元素 · 跳过 {conversion?.skipped_count ?? 0}</p>
        <p>Gate W / Mesh Validator：{mesh?.is_watertight ? 'watertight' : 'not watertight'}</p>
      </details>
      {props.designBounds && result.bounds_mm &&
        (Math.abs(props.designBounds.width - result.bounds_mm.size_x) > 0.1 ||
          Math.abs(props.designBounds.height - result.bounds_mm.size_y) > 0.1) &&
        <p className="manufacturing-notes" role="note">成品外接尺寸与二维预览不同；请以制造结果和 STL 尺寸为准。</p>}
      {notes.length > 0 && <div className="manufacturing-notes"><strong>提醒 / 检查信息</strong><ul>{[...new Set(notes)].map((note) => <li key={note}>{note}</li>)}</ul></div>}
    </div>}
    {props.projectWarnings.length > 0 && <div className="manufacturing-notes" role="note">
      {props.projectWarnings.join(' ')}
    </div>}
    <div className="manufacturing-output-actions">
      <button type="button" className="ui-secondary" onClick={props.onPreview} disabled={base ? !props.fabricPreviewResult : !result || !props.isCurrentResult(result.manufacturing_result_id)}>3D 预览</button>
      {!base && <StlExportButton result={result} status={status} projectName={props.projectName}
          isCurrentResult={props.isCurrentResult} />}
    </div>
  </section>
}
