import { useEffect, useId, useRef, useState } from 'react'
import type { FinalGeometry, PatternDocumentDTO } from '../model/types'
import { directSourceElement, millimetresPerUnit } from '../model/project'
import { ParameterPanel } from './ParameterPanel'
import { groupFor, type ParameterCatalog } from './parameterSchema'
import type { LayoutDraft } from './layoutDraft'
import type { PatternFamily } from '../api/pattern'
import {
  asRecord, ELEMENT_SPECS, FIELD_SPECS, fieldRecords, GRID_SPECS,
  gridModel, layoutModel, MAPPING_SPECS, placementState, POSITION_SPECS,
  scalarModifiers, stackModifiers, type NumericSpec,
} from './selectors'

export type EditAction =
  | { kind: 'element' | 'field' | 'scalar' | 'stack' | 'shape'; id: string; key: string; value: number | boolean | string }
  | { kind: 'grid'; key: string; value: number }
  | { kind: 'layout'; key: string; value: number | boolean }
  | { kind: 'field_add'; fieldType: string }
  | { kind: 'field_remove'; id: string }
  | { kind: 'field_enabled'; id: string; enabled: boolean }
  | { kind: 'field_binding'; id: string; fieldId: string }
  | { kind: 'modifier_add'; modifierType: 'size' | 'rotation' | 'position' }
  | { kind: 'modifier_remove'; lane: 'scalar' | 'stack'; id: string }

function NumericControl({ spec, value, onCommit, sliderMax = spec.max }: {
  spec: NumericSpec; value: number; onCommit: (value: number) => void; sliderMax?: number
}) {
  const inputId = useId()
  const [draft, setDraft] = useState(String(value))
  const draftRef = useRef(String(value))
  const committedRef = useRef(value)
  useEffect(() => {
    setDraft(String(value))
    draftRef.current = String(value)
    committedRef.current = value
  }, [value])
  const change = (next: string) => { draftRef.current = next; setDraft(next) }
  const commit = () => {
    const next = Number(draftRef.current)
    if (!draftRef.current.trim() || !Number.isFinite(next) || next < spec.min || next > spec.max
        || (spec.integer && !Number.isInteger(next))) {
      change(String(value))
      return
    }
    if (next !== committedRef.current) {
      committedRef.current = next
      onCommit(next)
    }
  }
  return <div className="parameter-control">
    <label htmlFor={inputId}>{spec.label}</label>
    <div className="parameter-inputs">
      <input type="range" aria-label={`${spec.label}滑杆`} min={spec.min} max={sliderMax} step={spec.integer ? spec.step : 'any'}
        value={draft.trim() && Number.isFinite(Number(draft))
          ? Math.min(sliderMax, Math.max(spec.min, Number(draft))) : Math.min(sliderMax, value)}
        onChange={(event) => change(event.target.value)} onPointerUp={commit} onKeyUp={commit} onBlur={commit} />
      <input id={inputId} type="number" min={spec.min} max={spec.max} step={spec.step}
        value={draft} onChange={(event) => change(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }} onBlur={commit} />
    </div>
  </div>
}

const fieldLabel: Record<string, string> = {
  constant: '固定场', linear: '线性场', ring: '环形场', wave: '波浪场',
  stripe: '条纹场', checker: '棋盘场', spiral: '螺旋场', noise: '有机噪声',
  image: '图片场', composite: '组合场',
}
const modifierLabel: Record<string, string> = {
  size: '尺寸', rotation: '旋转', position: '位置/变形', field_position: '场位移', density: '密度',
}
const positionParameterKeys: Record<string, string[]> = {
  offset: ['mode', 'offset_x', 'offset_y', 'strength'],
  attractor: ['mode', 'center_x', 'center_y', 'amount', 'radius', 'strength', 'falloff'],
  repeller: ['mode', 'center_x', 'center_y', 'amount', 'radius', 'strength', 'falloff'],
  radial_push: ['mode', 'center_x', 'center_y', 'amount', 'radius', 'strength', 'falloff'],
  twist: ['mode', 'center_x', 'center_y', 'angle', 'radius', 'strength', 'falloff'],
  wave: ['mode', 'center_x', 'center_y', 'angle', 'amount', 'wavelength', 'phase', 'radius', 'strength', 'falloff'],
}

export function InspectorControls({ dto, selected, onEdit, disabled, parameterCatalog = null,
  layoutSelection = null, layoutDraft = null, layoutBusy = false, onLayoutDraftEdit,
  selectedFieldId = '', onSelectField }: {
  dto: PatternDocumentDTO
  selected: FinalGeometry | null
  onEdit: (action: EditAction) => void
  disabled: boolean
  parameterCatalog?: ParameterCatalog | null
  layoutSelection?: PatternFamily | null
  layoutDraft?: LayoutDraft | null
  layoutBusy?: boolean
  onLayoutDraftEdit?: (key: string, value: number | boolean) => void
  selectedFieldId?: string
  onSelectField?: (id: string) => void
}) {
  const [newFieldType, setNewFieldType] = useState('')
  const fields = fieldRecords(dto)
  const activeField = fields.find((field) => field.id === selectedFieldId) ?? fields[0]
  const creatableTypes = Object.keys(parameterCatalog?.definitions.field ?? {})
    .filter((type) => type !== 'image' && type !== 'composite')
  const chosenType = creatableTypes.includes(newFieldType) ? newFieldType : creatableTypes[0] ?? ''
  const grid = gridModel(dto)
  const layout = layoutModel(dto)
  const stagedValues = layoutDraft?.proposal ? layoutSelection === 'grid'
    ? gridModel(layoutDraft.proposal) : layoutModel(layoutDraft.proposal)?.model : null
  const stagedGroup = layoutSelection ? groupFor(parameterCatalog, 'layout', layoutSelection) : null
  const placement = placementState(dto)
  const scale = millimetresPerUnit(dto.document) ?? 1
  const editable = selected ? directSourceElement(dto, selected.id, selected.x, selected.y) : null
  const replacements = asRecord(placement?.replacement_map) ?? {}
  const prototypes = asRecord(placement?.shape_prototypes) ?? {}

  return <fieldset disabled={disabled} className={`inspector-controls ${disabled ? 'controls-busy' : ''}`} aria-label="参数检查器">
    {selected && <section className="inspector-section" aria-label="元素变换">
      <h3>TRANSFORM / 元素变换</h3>
      <p className="inspector-id">{selected.id} · {selected.type}</p>
      {editable ? ELEMENT_SPECS.map((spec) => {
        const sourceValue = editable[spec.key]
        const value = typeof sourceValue === 'number' ? (spec.key === 'rotation' ? sourceValue : sourceValue * scale) : 0
        const sliderMax = spec.key === 'width' || spec.key === 'height'
          ? Math.min(spec.max, Math.max(10, value * 3)) : spec.max
        return <NumericControl key={spec.key} spec={spec} value={value} sliderMax={sliderMax}
          onCommit={(next) => onEdit({ kind: 'element', id: selected.id, key: spec.key, value: next })} />
      }) : <p className="inspector-readonly">派生元素或含效果的源元素仅可查看；不会猜测反向映射。</p>}
    </section>}

    {layoutSelection && <section className="inspector-section" aria-label="布局参数">
      <h3>LAYOUT / {stagedGroup?.label ?? '自由布局'}</h3>
      {layoutBusy ? <p className="inspector-readonly">正在由 Python 准备布局参数…</p>
        : layoutSelection === 'free' ? <p className="inspector-readonly">自由布局保留当前元素位置；点击“应用布局”才会确认。</p>
          : stagedGroup && stagedValues && layoutDraft?.family === layoutSelection
            ? <ParameterPanel key={`${layoutSelection}:${layoutDraft.sourceRevision}`} group={stagedGroup}
              values={stagedValues} onCommit={(key, value) => {
                if (typeof value !== 'string') onLayoutDraftEdit?.(key, value)
              }} />
            : <p className="inspector-readonly">布局参数暂不可用，请重新选择布局。</p>}
    </section>}

    {!layoutSelection && grid && <section className="inspector-section" aria-label="矩阵结构参数">
      <h3>PARAMETRIC / 矩阵结构</h3>
      {groupFor(parameterCatalog, 'layout', 'grid') ? <ParameterPanel group={groupFor(parameterCatalog, 'layout', 'grid')!}
        values={grid} onCommit={(key, value) => { if (typeof value === 'number') onEdit({ kind: 'grid', key, value }) }} />
        : GRID_SPECS.filter((item) => typeof grid[item.key] === 'number').map((item) =>
        <NumericControl key={item.key} spec={item} value={Number(grid[item.key])}
          onCommit={(next) => onEdit({ kind: 'grid', key: item.key, value: next })} />)}
      {Array.isArray(grid.basis_u_vector) && <p className="inspector-readonly">当前含斜向基向量；间距和旋转会同步调整基向量。</p>}
    </section>}

    {!layoutSelection && layout && (layout.mode === 'radial' || layout.mode === 'along_curve') &&
      groupFor(parameterCatalog, 'layout', layout.mode) &&
      <section className="inspector-section" aria-label="布局结构参数">
        <h3>LAYOUT / {groupFor(parameterCatalog, 'layout', layout.mode)!.label}</h3>
        <ParameterPanel group={groupFor(parameterCatalog, 'layout', layout.mode)!} values={layout.model}
          onCommit={(key, value) => { if (typeof value !== 'string') onEdit({ kind: 'layout', key, value }) }} />
      </section>}

    <section className="inspector-section" aria-label="参数场">
      <h3>FIELD / 参数场</h3>
      <div className="field-create">
        <label htmlFor="field-type">参数场类型</label>
        <select id="field-type" value={chosenType} disabled={!chosenType}
          onChange={(event) => setNewFieldType(event.target.value)}>
          {creatableTypes.map((type) => <option key={type} value={type}>
            {parameterCatalog?.definitions.field[type]?.label ?? fieldLabel[type] ?? type}
          </option>)}
        </select>
        <button type="button" disabled={!chosenType}
          onClick={() => onEdit({ kind: 'field_add', fieldType: chosenType })}>＋ 添加参数场</button>
      </div>
      <p className="inspector-readonly">参数场由下方效果层引用后才会改变图案；同一参数场可驱动多个效果层。</p>
      {fields.length > 0 && <label className="field-picker">选择已有参数场
        <select value={String(activeField?.id ?? '')} onChange={(event) => onSelectField?.(event.target.value)}>
          {fields.map((field) => <option key={String(field.id)} value={String(field.id)}>
            {fieldLabel[String(field.type)] ?? String(field.type)} · {String(field.id)}
          </option>)}
        </select>
      </label>}
      {activeField && (() => {
        const type = String(activeField.type)
        const parameters = asRecord(activeField.parameters) ?? {}
        const controls = type === 'composite'
          ? <p className="inspector-readonly">组合场只读：A={String(parameters.input_a_field_id ?? '—')}，B={String(parameters.input_b_field_id ?? '—')}，运算={String(parameters.operator ?? '—')}。原始引用完整保留。</p>
          : null
        const group = groupFor(parameterCatalog, 'field', type)
        return <>
          <label className="parameter-toggle"><input type="checkbox" checked={activeField.enabled !== false}
            onChange={(event) => onEdit({ kind: 'field_enabled', id: String(activeField.id), enabled: event.target.checked })} />启用参数场</label>
          <button type="button" onClick={() => onEdit({ kind: 'field_remove', id: String(activeField.id) })}>删除参数场</button>
          {controls ?? (group ? <ParameterPanel group={group} values={parameters}
          onCommit={(key, value) => onEdit({ kind: 'field', id: String(activeField.id), key, value })} />
            : type === 'image' || !FIELD_SPECS[type] ? <p className="inspector-readonly">该参数场当前只读；图片资产尚未接入网页。</p>
              : <>{FIELD_SPECS[type].filter((item) => typeof parameters[item.key] === 'number').map((item) =>
            <NumericControl key={`${activeField.id}-${item.key}`} spec={item} value={Number(parameters[item.key])}
              onCommit={(next) => onEdit({ kind: 'field', id: String(activeField.id), key: item.key, value: next })} />)}
          {typeof parameters.invert === 'boolean' && <label className="parameter-toggle">
            <input type="checkbox" checked={parameters.invert} onChange={(event) =>
              onEdit({ kind: 'field', id: String(activeField.id), key: 'invert', value: event.target.checked })} />反转
          </label>}</>)}
        </>
      })()}
    </section>

    <section className="inspector-section" aria-label="效果堆栈">
        <h3>MODIFIERS / 效果堆栈</h3>
        <div className="modifier-actions">
          <button type="button" disabled={!fields.length || !groupFor(parameterCatalog, 'modifier', 'size')}
            onClick={() => onEdit({ kind: 'modifier_add', modifierType: 'size' })}>＋ 尺寸</button>
          <button type="button" disabled={!fields.length || !groupFor(parameterCatalog, 'modifier', 'rotation')}
            onClick={() => onEdit({ kind: 'modifier_add', modifierType: 'rotation' })}>＋ 旋转</button>
          <button type="button" disabled={!groupFor(parameterCatalog, 'modifier', 'position')}
            onClick={() => onEdit({ kind: 'modifier_add', modifierType: 'position' })}>＋ 位置/变形</button>
        </div>
        {!fields.length && <p className="inspector-readonly">先添加参数场，即可新增尺寸或旋转效果层。</p>}
        <p className="inspector-readonly">求值顺序：场驱动层 → 有序变形层。当前引擎不支持跨组拖动排序。</p>
        {scalarModifiers(dto).map((modifier) => {
          const id = String(modifier.id)
          const type = String(modifier.type)
          const mapping = asRecord(modifier.mapping) ?? {}
          return <div className="modifier-card" key={`scalar-${id}`}>
            <label className="parameter-toggle"><input type="checkbox" checked={modifier.enabled !== false}
              onChange={(event) => onEdit({ kind: 'scalar', id, key: 'enabled', value: event.target.checked })} />
              {modifierLabel[type] ?? type} · {id}</label>
            {(type === 'size' || type === 'rotation') && <label className="field-picker">驱动参数场
              <select value={String(modifier.field_id ?? '')} onChange={(event) =>
                onEdit({ kind: 'field_binding', id, fieldId: event.target.value })}>
                {!fields.some((field) => field.id === modifier.field_id) &&
                  <option value={String(modifier.field_id ?? '')}>缺失：{String(modifier.field_id ?? '—')}</option>}
                {fields.map((field) => <option key={String(field.id)} value={String(field.id)}>
                  {fieldLabel[String(field.type)] ?? String(field.type)} · {String(field.id)}
                </option>)}
              </select>
            </label>}
            {(type === 'size' || type === 'rotation') && groupFor(parameterCatalog, 'modifier', type)
              ? <ParameterPanel group={groupFor(parameterCatalog, 'modifier', type)!} values={mapping}
                onCommit={(key, value) => onEdit({ kind: 'scalar', id, key, value })} />
              : (type === 'size' || type === 'rotation') && MAPPING_SPECS.filter((item) => typeof mapping[item.key] === 'number').map((item) =>
              <NumericControl key={item.key} spec={item} value={Number(mapping[item.key])}
                onCommit={(next) => onEdit({ kind: 'scalar', id, key: item.key, value: next })} />)}
            {type === 'density' && typeof modifier.threshold === 'number' &&
              <NumericControl spec={{ key: 'threshold', label: '阈值', min: 0, max: 1, step: 0.01 }}
                value={modifier.threshold} onCommit={(next) => onEdit({ kind: 'scalar', id, key: 'threshold', value: next })} />}
            <button type="button" onClick={() => onEdit({ kind: 'modifier_remove', lane: 'scalar', id })}>删除效果层</button>
          </div>
        })}
        {stackModifiers(dto).map((modifier) => {
          const id = String(modifier.id)
          const type = String(modifier.type)
          const parameters = asRecord(modifier.parameters) ?? {}
          return <div className="modifier-card" key={`stack-${id}`}>
            <label className="parameter-toggle"><input type="checkbox" checked={modifier.enabled !== false}
              onChange={(event) => onEdit({ kind: 'stack', id, key: 'enabled', value: event.target.checked })} />
              {modifierLabel[type] ?? type} · {id}</label>
            {type === 'position' && groupFor(parameterCatalog, 'modifier', 'position')
              ? <ParameterPanel group={{ ...groupFor(parameterCatalog, 'modifier', 'position')!,
                parameters: groupFor(parameterCatalog, 'modifier', 'position')!.parameters.filter((item) =>
                  (positionParameterKeys[String(parameters.mode ?? 'offset')] ?? positionParameterKeys.offset).includes(item.id)) }}
                values={parameters} onCommit={(key, value) =>
                  onEdit({ kind: 'stack', id, key, value })} />
              : type === 'position' ? POSITION_SPECS.filter((item) => typeof parameters[item.key] === 'number').map((item) =>
                <NumericControl key={item.key} spec={item} value={Number(parameters[item.key])}
                  onCommit={(next) => onEdit({ kind: 'stack', id, key: item.key, value: next })} />)
              : <small>此有序层可启用/停用；详细参数暂由桌面版编辑。</small>}
            <button type="button" onClick={() => onEdit({ kind: 'modifier_remove', lane: 'stack', id })}>删除效果层</button>
          </div>
        })}
        {placement && selected && <div className="modifier-card shape-replacement">
          <label htmlFor="shape-replacement">形状替换 · {selected.id}</label>
          <select id="shape-replacement" value={String(replacements[selected.id] ?? '')}
            onChange={(event) => onEdit({ kind: 'shape', id: selected.id, key: 'prototype', value: event.target.value })}>
            <option value="">保持原形</option>
            {Object.keys(prototypes).map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
          <small>形状分配在效果层前执行，仅替换当前选中元素，不修改原始元素。</small>
        </div>}
    </section>
  </fieldset>
}
