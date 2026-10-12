import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ManufacturingBuildResult } from '../api/manufacturing'
import type { ManufacturingStatus } from './useManufacturing'
import { StlExportButton } from './StlExportButton'
import { ParameterPanel } from '../document/ParameterPanel'
import { ParameterInteraction } from '../document/ParameterInteraction'
import { fabricBase, fabricOutputMode, type FabricBaseType, type FabricOutputMode } from '../document/fabricBase'
import { fabricUnitCell, fabricPlacement, unitCellChoices, type UnitCellType } from '../document/fabricCell'
import { availableFabricFields, directionalHeightField, waveHeightField, centerHeightField, fabricFieldModifier, fabricModifierTypes, type FabricModifierType } from '../document/fabricModifiers'
import { groupFor, type ParameterCatalog, type ParameterValue } from '../document/parameterSchema'
import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { FabricPreflightPanel } from './FabricPreflightPanel'
import { FabricFusionPanel } from './FabricFusionPanel'
import { fabricPresets, directionalFabricRecipe, waveFabricRecipe, centerFabricRecipe } from '../document/fabricPresets'
import { fabricDesignWarnings, fabricPreviewSummary } from '../document/fabricDesignSummary'
import { FABRIC_PREVIEW_NOTICE, fabricExportNotice } from './fabricCopy'
import { formatMm } from '../model/formatMm'
import { RealSizePanel } from './RealSizePanel'
import { InspectorSection } from '../document/InspectorSection'
import { isOriginalShape, originalShape } from '../document/fabricOriginal'

interface Props {
  actionHost?: HTMLElement | null
  parametersDisabled?: boolean
  onUnitCellDraft?: (key: string, value: ParameterValue | null) => void
  canUseInputs?: () => boolean
  heightText: string
  onHeightChange: (value: string) => void
  validHeight: boolean
  canBuild: boolean
  computeBusy?: boolean
  isComputeBusy?: () => boolean
  recipeSaving?: boolean
  onHeightEffect?: (mode: 'uniform' | 'directional' | 'wave' | 'center') => void
  onDirectionalHeightParameter?: (key: string, value: ParameterValue) => void
  onWaveHeightParameter?: (key: string, value: ParameterValue) => void
  onCenterHeightParameter?: (key: string, value: ParameterValue) => void
  heightSyncToken?: string
  onHeightPending?: (id: string, pending: boolean) => void
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
  parameterLoad?: { status: 'loading' | 'ready' | 'error'; error?: string }
  onRetryParameters?: () => void
  onFabricType: (type: FabricBaseType | 'none') => void
  onOutputMode?: (mode: FabricOutputMode) => void
  onFabricParameter: (key: string, value: ParameterValue) => void
  onUnitCellType: (type: UnitCellType | 'none' | 'original') => void
  onOriginalShapeParameter?: (key: string, value: ParameterValue) => void
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
  const original = isOriginalShape(props.document)
  const outputMode = original && !base ? 'cells_only' : fabricOutputMode(props.document)
  const shapeReady = Boolean(cellOrOriginal())
  function cellOrOriginal() { return original || fabricUnitCell(props.document) }
  const originalGroup = groupFor(props.parameterCatalog, 'fabric_original', 'original')
  const originalValues: Record<string, unknown> | null = originalShape(props.document) ?? (originalGroup ? {
    ...Object.fromEntries(originalGroup.parameters.map(p => [p.id, p.default])), height_mm: Number(props.heightText),
  } : null)
  const fabricGroup = base && groupFor(props.parameterCatalog, 'fabric_base', base.type)
  const cell = fabricUnitCell(props.document)
  const placement = fabricPlacement(props.document)
  const cellGroup = cell && groupFor(props.parameterCatalog, 'fabric_cell', cell.type)
  const placementGroup = placement && groupFor(props.parameterCatalog, 'fabric_placement', 'regular')
  const parameterStatus = props.parameterLoad?.status ?? (props.parameterCatalog ? 'ready' : 'error')
  const canSelectCell = (type: UnitCellType) => parameterStatus === 'ready'
    && Boolean(groupFor(props.parameterCatalog, 'fabric_cell', type))
    && Boolean(placement || groupFor(props.parameterCatalog, 'fabric_placement', 'regular'))
  const selectCell = (type: UnitCellType | 'none' | 'original') => {
    if (type === 'original' ? originalGroup && parameterStatus === 'ready' : type === 'none' || canSelectCell(type)) props.onUnitCellType(type)
  }
  const fabricFields = availableFabricFields(props.document)
  const summary = fabricPreviewSummary(props.document,
    props.fabricPreviewStatus === 'ready' ? props.fabricPreviewResult : null)
  const designWarnings = fabricDesignWarnings(props.document)
  const [currentSection, setCurrentSection] = useState<'shape' | 'height' | 'output' | 'preview' | null>('shape')
  const sectionProps = (key: 'shape' | 'height' | 'output' | 'preview') => ({ expanded: currentSection === key, onExpandedChange: (open: boolean) => setCurrentSection(open ? key : null) })
  const [presetId, setPresetId] = useState<string>(directionalFabricRecipe.id)
  const recipeId = (props.document?.document.metadata.web_fabric_recipe as { id?: string } | undefined)?.id
  useEffect(() => {
    setPresetId(recipeId === centerFabricRecipe.id ? centerFabricRecipe.id : recipeId === waveFabricRecipe.id ? waveFabricRecipe.id : directionalFabricRecipe.id)
  }, [props.document?.document_id, recipeId])
  const height = fabricFieldModifier(props.document, 'height')
  const directionField = directionalHeightField(props.document)
  const directional = height?.enabled && directionField?.id === height.field_id
  const directionParameters = directionField?.parameters as Record<string, ParameterValue> | undefined
  const waveField = waveHeightField(props.document)
  const waving = height?.enabled && waveField?.id === height.field_id
  const waveParameters = waveField?.parameters as Record<string, ParameterValue> | undefined
  const waveGroup = groupFor(props.parameterCatalog, 'field', 'wave')
  const centerField = centerHeightField(props.document)
  const centered = height?.enabled && centerField?.id === height.field_id
  const centerParameters = centerField?.parameters as Record<string, ParameterValue> | undefined
  const ringGroup = groupFor(props.parameterCatalog, 'field', 'ring')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  useEffect(() => {
    if (status !== 'building') return
    const started = performance.now()
    setElapsedSeconds(0)
    const timer = window.setInterval(() => setElapsedSeconds((performance.now() - started) / 1000), 100)
    return () => window.clearInterval(timer)
  }, [status])
  useEffect(() => {
    if (status === 'building' || status === 'error') setCurrentSection('preview')
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
  const standardActions = <div className="manufacturing-output-actions">
    <button type="button" className="ui-primary" onClick={props.onBuild}
      disabled={!props.canBuild || props.computeBusy || status === 'building'}>检查并生成</button>
    <StlExportButton result={result} status={status} projectName={props.projectName} isCurrentResult={props.isCurrentResult} />
  </div>
  return <ParameterInteraction.Provider value={{ syncToken: props.heightSyncToken ?? '', onPending: props.onHeightPending }}>
    <section className="manufacturing-panel" aria-label="制造检查" onClickCapture={event => {
      const button = (event.target as Element).closest('button')
      if (button && !button.disabled && /生成最终|检查并生成|检查可制造性|更新3D预览/.test(button.textContent ?? '')) setCurrentSection('preview')
    }}>
    <div className="manufacturing-heading"><span className="eyebrow">{base ? 'FABRIC DESIGN PREVIEW' : 'FINAL MANUFACTURING MESH'}</span><h1>{base ? 'Fabric 设计预览' : '制造检查'}</h1>
      <small>设计预览不代表最终制造通过。</small>
      <button type="button" className="workflow-back" onClick={props.onBackDesign}>返回设计</button></div>
    <section className="manufacturing-settings" aria-label="Fabric Base">
      <fieldset disabled={props.recipeSaving || props.parametersDisabled} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
      {(base || original) && <section aria-label="Fabric Unit Cell">
        <InspectorSection title="形状与单元" label="单元尺寸设置" icon="shape" {...sectionProps('shape')}>
        <label htmlFor="fabric-cell-type">Unit Cell 类型</label>
        {parameterStatus === 'loading' && <p role="status">正在加载单元参数…</p>}
        {parameterStatus === 'error' && <div role="alert"><p>{props.parameterLoad?.error ?? '单元参数未加载成功。'}</p>
          {props.onRetryParameters && <button type="button" onClick={props.onRetryParameters}>重试加载单元参数</button>}</div>}
        {parameterStatus === 'ready' && cell && !cellGroup && <p role="alert">后端未提供当前单元 {cell.type} 的参数定义；可选择其他受支持单元或重试加载。</p>}
        <select id="fabric-cell-type" value={original ? 'original' : cell?.type ?? 'none'} disabled={parameterStatus !== 'ready'} onChange={(event) => {
          const type = event.target.value as UnitCellType | 'none' | 'original'
          selectCell(type)
          // A rejected synchronous edit must not leave an uncontrolled native selection.
          event.target.value = original ? 'original' : cell?.type ?? 'none'
        }}>
          <option value="original" disabled={!originalGroup}>保留原图形状（默认）</option>
          {!original && !cell && <option value="none" disabled>旧无单元配置：请选择原图或单元</option>}
          {unitCellChoices.map(item => <option key={item.type} value={item.type}
            disabled={!canSelectCell(item.type)}>{item.label} · {item.type}{canSelectCell(item.type) ? '' : '（参数不可用）'}</option>)}
        </select>

        {!cell && !original && <p role="status">旧无单元数据已保留；请选择“保留原图形状”启用新的原图模式，或选择一种单元。不会生成空 STL。</p>}
        {original && <>
          {!originalGroup && <p role="alert">后端尚未提供原图形状参数，请重试加载参数。</p>}
          {originalGroup && originalValues && <ParameterPanel group={{ ...originalGroup, parameters: originalGroup.parameters.map(p =>
            p.id === 'size_scale' ? { ...p, label: '图形大小', unit: '%', min: p.min == null ? p.min : p.min * 100, max: p.max == null ? p.max : p.max * 100,
              default: Number(p.default) * 100, step: 1, slider_min: p.slider_min == null ? undefined : p.slider_min * 100,
              slider_max: p.slider_max == null ? undefined : p.slider_max * 100, slider_step: 1 } : p) }}
            values={{ ...originalValues, size_scale: Number(originalValues.size_scale) * 100 }}
            onDraft={(key, value) => props.onUnitCellDraft?.(key === 'size_scale' ? 'original_size_scale' : key,
              typeof value === 'number' && key === 'size_scale' ? value / 100 : value)}
            onCommit={(key, value) => props.onOriginalShapeParameter?.(key, key === 'size_scale' ? Number(value) / 100 : value)} />}
          <small>仅调整图形，不改变点距；高度效果可叠加。</small>
          {fabricFieldModifier(props.document, 'scale')?.enabled && <p>仍叠加已有 Fabric 比例场；百分比是本层轮廓倍率，不代表每个元素最终尺寸相同。</p>}
        </>}
        {cell && cellGroup && <><h2>单元大小与高度</h2><ParameterPanel
          group={{ label: '单元尺寸', parameters: cellGroup.parameters.filter(p => p.id === 'width_mm' || p.id === 'height_mm').map(p =>
            p.id === 'width_mm' ? { ...p, id: 'uniform_size_mm', label: '单元大小' } : { ...p, label: '单元高度' }) }}
          values={{ uniform_size_mm: cell.width_mm, height_mm: cell.height_mm }}
          onDraft={props.onUnitCellDraft}
          onCommit={(key, value) => props.onUnitCellParameter('cell', key, value)} />
          <p>大小控件保持当前宽深比例，只改变单元，不改变点位与点距。</p>
          <details><summary>高级：精确宽深与尺寸继承</summary><ParameterPanel group={cellGroup}
          values={{ ...cell, size_mode: cell.size_mode ?? 'follow_pattern' }}
          onCommit={(key, value) => props.onUnitCellParameter('cell', key, value)} /></details>
          <details className="parameter-help"><summary>尺寸继承说明</summary><p>固定尺寸不继承二维大小；跟随图案按最终二维尺寸比例调整宽深。Fabric 比例场在两种模式下仍可叠加。</p></details>
        </>}

        <details className="parameter-extra"><summary>高级：造型、布点与尺寸说明</summary>
        <div className="unit-cell-choices" aria-label="单元造型缩略图">{unitCellChoices.map(item => <button type="button"
          key={item.type} title={item.label} aria-label={`选择${item.label}`} aria-pressed={cell?.type === item.type}
          disabled={!canSelectCell(item.type)} onClick={() => selectCell(item.type)}><svg viewBox="0 0 32 32" aria-hidden="true"><path d={item.path} /></svg><span>{item.label}</span></button>)}</div>
        {parameterStatus === 'ready' && props.onRetryParameters && <button type="button" onClick={props.onRetryParameters}>重新加载单元参数</button>}
        {original && <p>使用已应用的最终二维轮廓和孔洞，保留位置、相对大小与旋转；逐元素挤出，不铺满区域。</p>}
        <InspectorSection title="布点方式" label="单元布点设置" defaultExpanded={false}>
        {original && <p>原图形状固定跟随最终二维元素分布。保留的全区域／Pattern Points 设置仅在替换单元模式使用，不会暗中重复轮廓。</p>}
        {!cell && !original && <p role="status">请先选择形状；暂无可编辑的布点参数。</p>}
        {cell && !placement && <p role="alert">当前作品缺少布点配置，布点暂不可编辑。</p>}
        {cell && placement && <><label htmlFor="fabric-placement-mode">布点方式</label>
          <select id="fabric-placement-mode" value={placement.mode ?? 'area_fill'}
            onChange={(event) => props.onPlacementMode(event.target.value as 'area_fill' | 'pattern_points')}>
            <option value="area_fill">全区域</option><option value="pattern_points">按图案元素</option>
          </select></>}
        {cell && placement && (placement.mode ?? 'area_fill') === 'area_fill' && placementGroup &&
          <ParameterPanel group={placementGroup} values={{ ...placement }}
            onCommit={(key, value) => props.onUnitCellParameter('placement', key, value)} />}
        {cell && placement && (placement.mode ?? 'area_fill') === 'area_fill' && !placementGroup && <p role="status">
          {parameterStatus === 'loading' ? '正在加载布点参数…' : parameterStatus === 'error'
            ? `布点参数加载失败：${props.parameterLoad?.error ?? '请重试加载单元参数。'}`
            : '后端未提供 regular 布点参数定义；已保留当前布点设置，请重试加载参数。'}</p>}
        {cell && (placement?.mode ?? 'area_fill') === 'pattern_points' && <p>图案元素：{props.fabricPreviewResult?.element_count ?? '待更新'} · 单元实例：{props.fabricPreviewResult?.total_count ?? '待更新'}</p>}
        </InspectorSection>
        </details>
        </InspectorSection>
        {props.document && <InspectorSection title="高度与变化" label="直接高度控制" icon="height" {...sectionProps('height')}>
          {shapeReady && props.onHeightEffect && <><label htmlFor="fabric-height-effect">高度变化</label>
          <select id="fabric-height-effect" value={!height?.enabled ? 'uniform' : directional ? 'directional' : waving ? 'wave' : centered ? 'center' : 'advanced'}
            onChange={event => props.onHeightEffect?.(event.target.value as 'uniform' | 'directional' | 'wave' | 'center')}>
            <option value="uniform">均匀高度</option><option value="directional">沿方向变化</option>
            <option value="wave" disabled={!waveGroup}>波浪起伏</option>
            <option value="center" disabled={!ringGroup}>中心隆起</option>
            {height?.enabled && !directional && !waving && !centered && <option value="advanced" disabled>高级参数场绑定</option>}
          </select>
          {!height?.enabled && <p>使用上方单元高度，不需要创建参数场。</p>}
          {directional && <>
            {groupFor(props.parameterCatalog, 'field', 'linear') && <ParameterPanel
              group={{ label: '方向', parameters: groupFor(props.parameterCatalog, 'field', 'linear')!.parameters.filter(p => p.id === 'angle') }}
              values={{ angle: directionParameters?.angle ?? 0 }} onCommit={props.onDirectionalHeightParameter!} />}
            {groupFor(props.parameterCatalog, 'fabric_modifier', 'height') && <ParameterPanel
              group={groupFor(props.parameterCatalog, 'fabric_modifier', 'height')!} values={{ ...height }}
              onCommit={props.onDirectionalHeightParameter!} />}
          </>}
          {waving && waveGroup && <>
            <ParameterPanel group={{ ...waveGroup, parameters: waveGroup.parameters.filter(p => p.id === 'wavelength' || p.id === 'angle')
              .map(p => p.id === 'angle' ? { ...p, label: '波浪方向' } : p) }}
              values={{ ...waveParameters }} onCommit={props.onWaveHeightParameter!} />
            {groupFor(props.parameterCatalog, 'fabric_modifier', 'height') && <ParameterPanel
              group={groupFor(props.parameterCatalog, 'fabric_modifier', 'height')!} values={{ ...height }}
              onCommit={props.onWaveHeightParameter!} />}
            <details><summary>高级：波浪相位与形态</summary>
              <ParameterPanel group={{ ...waveGroup, parameters: waveGroup.parameters.filter(p => p.id !== 'wavelength' && p.id !== 'angle')
                .map(p => p.id === 'phase' ? { ...p, label: '相位（弧度）' } : p) }}
                values={{ ...waveParameters }} onCommit={props.onWaveHeightParameter!} />
            </details>
            <p>波长使用世界毫米；波浪以世界原点和相位定位，不随相机移动。滑杆松手／数值确认后自动更新预览，不执行最终制造。</p>
          </>}
          {centered && ringGroup && <>
            <ParameterPanel group={{ label: '中心隆起', parameters: ringGroup.parameters
              .filter(p => ['center_x', 'center_y', 'ring_width'].includes(p.id)).map(p => p.id === 'ring_width'
                ? { ...p, id: 'range_mm', label: '影响范围', default: Number(p.default) / 2, value: Number(p.value) / 2,
                  min: p.min == null ? p.min : p.min / 2, max: p.max == null ? p.max : p.max / 2,
                  step: p.step == null ? p.step : p.step / 2,
                  slider_min: p.slider_min == null ? p.slider_min : p.slider_min / 2,
                  slider_max: p.slider_max == null ? p.slider_max : p.slider_max / 2,
                  slider_step: p.slider_step == null ? p.slider_step : p.slider_step / 2 }
                : { ...p, label: p.id === 'center_x' ? '中心 X' : '中心 Y' }) }}
              values={{ ...centerParameters, range_mm: Number(centerParameters?.ring_width) / 2 }}
              onCommit={props.onCenterHeightParameter!} />
            {groupFor(props.parameterCatalog, 'fabric_modifier', 'height') && <ParameterPanel
              group={groupFor(props.parameterCatalog, 'fabric_modifier', 'height')!} values={{ ...height }}
              onCommit={props.onCenterHeightParameter!} />}
            <p>中心与影响半径使用世界毫米；中心高、向外线性降低，边界及范围外保持最低高度，不隐藏外围图案。
              按元素／实例位置采样，离散点阵不一定达到理论最高高度。滑杆松手／数值确认后自动更新预览，不执行最终制造。</p>
          </>}
          </>}<details className="parameter-help"><summary>高度与尺寸叠加说明</summary><p>基础尺寸不等于最终尺寸：跟随二维大小及已启用的 Fabric 比例仍会叠加；均匀高度不会关闭这些效果。</p></details>
      {props.document && <InspectorSection title="效果预设" label="Fabric Preset" defaultExpanded={false}>
        <label htmlFor="fabric-preset">Fabric 预设</label>
        <select id="fabric-preset" value={presetId} onChange={(event) => setPresetId(event.target.value)}>
          <option value={directionalFabricRecipe.id}>{directionalFabricRecipe.label} · 完整效果配方</option>
          <option value={waveFabricRecipe.id}>{waveFabricRecipe.label} · 完整效果配方</option>
          <option value={centerFabricRecipe.id} disabled={!ringGroup}>{centerFabricRecipe.label} · 完整效果配方</option>
          {fabricPresets.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
        </select>
        <button type="button" className="ui-secondary" disabled={props.recipeSaving} onClick={() => props.onFabricPreset(presetId)}>
          {props.recipeSaving ? '正在保护当前作品…' : '应用预设'}</button>
        {recipeId === directionalFabricRecipe.id &&
          <button type="button" className="ui-secondary" disabled={props.recipeSaving}
            onClick={() => props.onFabricPreset(directionalFabricRecipe.id)}>恢复方向渐变配方</button>}
        {recipeId === waveFabricRecipe.id &&
          <button type="button" className="ui-secondary" disabled={props.recipeSaving}
            onClick={() => props.onFabricPreset(waveFabricRecipe.id)}>恢复波浪起伏配方</button>}
        {recipeId === centerFabricRecipe.id && <button type="button" className="ui-secondary" disabled={props.recipeSaving}
          onClick={() => props.onFabricPreset(centerFabricRecipe.id)}>恢复中心隆起配方</button>}
        {[directionalFabricRecipe.id, waveFabricRecipe.id, centerFabricRecipe.id].some(id => id === presetId) && <p>应用高度效果：保留当前原图／单元造型、大小、布点、输出和基底；仅设置专用高度场与 2–6mm 范围。恢复配方仅重置高度与该配方的场参数。</p>}
        {fabricPresets.find(p => p.id === presetId) && <p>这是包含造型替换的完整预设：将改为 {unitCellChoices.find(c => c.type === fabricPresets.find(p => p.id === presetId)!.cell.type)?.label}，
          并设置该预设的布点和基底参数；不只修改高度。</p>}
      </InspectorSection>}
        {shapeReady && <InspectorSection title="高级参数场绑定" label="Fabric Field Modifiers" defaultExpanded={false}>
          <p>高级绑定使用当前设计的 Shared Field 控制实例；预览与最终制造使用同一实例计划。</p>
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
        </InspectorSection>}

        </InspectorSection>}
        {cell && <p>{FABRIC_PREVIEW_NOTICE} {fabricExportNotice(props.fabricStlTestExportEnabled)}</p>}
      </section>}
      <InspectorSection title="基底与输出模式" label="制造输出方式" icon="output" {...sectionProps('output')}>
      <label htmlFor="generation-method">生成方式</label>
      <select id="generation-method" value={original ? 'contour' : 'cells'} onChange={(event) => {
        const stored = (props.document?.document.metadata.fabric_config as { unit_cell?: { type: UnitCellType } } | undefined)?.unit_cell
        props.onUnitCellType(event.target.value === 'contour' ? 'original' : stored?.type ?? 'original')
      }}>
        <option value="contour">按原图轮廓挤出</option><option value="cells">使用立体单元</option>
      </select>
      <p>生成方式与下方造型同步；要替换原图，请选择具体单元造型。</p>
      {(base || original) && <><label htmlFor="fabric-output-mode">单元输出</label>
        <select id="fabric-output-mode" value={outputMode} onChange={event => props.onOutputMode?.(event.target.value as FabricOutputMode)}>
          <option value="cells_only">仅图案单元</option><option value="cells_with_base">单元＋基底</option>
        </select>
        {outputMode === 'cells_with_base' && base && <><label htmlFor="fabric-base-type">基底类型</label>
          <select id="fabric-base-type" value={base.type} onChange={event => props.onFabricType(event.target.value as FabricBaseType)}>
            <option value="solid">Solid 实心基底</option><option value="grid">Grid 网格基底</option>
          </select></>}
        <p>{outputMode === 'cells_only' ? '不生成实体基底；单元从 Z=0 开始，可包含多个独立封闭实体。布点仍使用设计范围。' : '基底使用最终二维外接范围；Solid 填满矩形，Grid 生成网孔。'}</p>
        <details><summary>{outputMode === 'cells_only' ? '高级：布点范围边距与保留的基底配置' : '高级：基底参数'}</summary>
          {fabricGroup && <ParameterPanel group={{ ...fabricGroup, parameters: fabricGroup.parameters.filter(p => outputMode !== 'cells_only' || p.id === 'margin_mm') }} values={{ ...base }} onCommit={props.onFabricParameter} />}
        </details></>}
    {props.document && <InspectorSection title="高级：真实尺寸" label="制造真实尺寸" defaultExpanded={false}>
      <p>图案范围：{props.designBounds ? `${formatMm(props.designBounds.width)} × ${formatMm(props.designBounds.height)} mm` : '待求值'}</p>
      <details><summary>查看或调整真实尺寸</summary><RealSizePanel document={props.document} bounds={props.designBounds ?? null}
        disabled={!props.canEditSize} onConfirm={(width, height) => props.onConfirmRealSize?.(width, height)} /></details>
    </InspectorSection>}
      </InspectorSection>
      </fieldset>
    </section>
    <InspectorSection title="预览与最终制造" label="预览与最终制造" icon="manufacture" {...sectionProps('preview')}>
    <div className="manufacturing-settings">
      {!base && <><label htmlFor="manufacturing-height">厚度 <span>mm</span></label>
        <input id="manufacturing-height" type="number" min="0.01" step="0.1" value={props.heightText}
          onChange={(event) => props.onHeightChange(event.target.value)} /></>}
      {(base || !props.actionHost) && <button type="button" className="ui-primary" onClick={base ? props.onUpdateFabricPreview : props.onBuild}
        disabled={!props.canBuild || (base && !shapeReady) || props.computeBusy || (base ? props.fabricPreviewStatus === 'building' : status === 'building')}>
        {base ? '更新3D预览' : '检查并生成'}</button>}
      {base && <small>大小／均匀高度拖动即时显示；其余数值松手后自动更新。此按钮用于手动重试。</small>}
    </div>
    {props.computeBusy && <p role="status">计算任务正在执行；请等待完成后再发起预览、预检或制造。</p>}
    {base && props.document && <FabricPreflightPanel document={props.document}
      canUseInputs={() => shapeReady && (props.canUseInputs?.() ?? true)}
      fetcher={props.candidateFetcher} disabled={!props.canBuild || !shapeReady} computeBusy={props.computeBusy} isComputeBusy={props.isComputeBusy} />}
    {base && props.document && <FabricFusionPanel document={props.document}
      canUseInputs={() => shapeReady && (props.canUseInputs?.() ?? true)}
      fetcher={props.candidateFetcher} disabled={!props.canBuild || !shapeReady} computeBusy={props.computeBusy} isComputeBusy={props.isComputeBusy}
      actionHost={props.actionHost}
      testExportEnabled={props.fabricStlTestExportEnabled} />}
    {!props.validHeight && <p className="manufacturing-error" role="alert">厚度必须大于 0 mm。</p>}
    <div className={`manufacturing-status ${base ? props.fabricPreviewStatus : status}`} role="status">
      {base ? !shapeReady ? '旧配置未选择形状，请启用原图或选择单元' : ({ idle: '尚未更新设计预览', building: '正在更新3D预览…', ready: '设计预览已就绪',
        stale: '设计已变化，请更新3D预览', error: '设计预览失败' }[props.fabricPreviewStatus]) : labels[status]}</div>
    {base && props.fabricPreviewError && <p className="manufacturing-error" role="alert">{props.fabricPreviewError}</p>}
    {shapeReady && props.fabricPreviewStatus === 'ready' && props.fabricPreviewResult && <><p>可见单元：{props.fabricPreviewResult.active_count} / {props.fabricPreviewResult.total_count}</p>
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
      {!base && !props.actionHost && <StlExportButton result={result} status={status} projectName={props.projectName}
          isCurrentResult={props.isCurrentResult} />}
    </div>
    </InspectorSection>
    {!base && props.actionHost && createPortal(standardActions, props.actionHost)}
  </section></ParameterInteraction.Provider>
}
