import { useEffect, useId, useRef, useState } from 'react'
import type { FinalGeometry, PatternDocumentDTO } from '../model/types'
import { directSourceElement, millimetresPerUnit } from '../model/project'
import {
  asRecord, ELEMENT_SPECS, FIELD_SPECS, fieldRecords, GRID_SPECS,
  gridModel, MAPPING_SPECS, placementState, POSITION_SPECS,
  scalarModifiers, stackModifiers, type NumericSpec,
} from './selectors'

export type EditAction =
  | { kind: 'element' | 'field' | 'scalar' | 'stack' | 'shape'; id: string; key: string; value: number | boolean | string }
  | { kind: 'grid'; key: string; value: number }

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

export function InspectorControls({ dto, selected, onEdit, disabled }: {
  dto: PatternDocumentDTO
  selected: FinalGeometry | null
  onEdit: (action: EditAction) => void
  disabled: boolean
}) {
  const [fieldId, setFieldId] = useState<string>('')
  const fields = fieldRecords(dto)
  const activeField = fields.find((field) => field.id === fieldId) ?? fields[0]
  const grid = gridModel(dto)
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
      {placement && <div className="shape-replacement">
        <label htmlFor="shape-replacement">形状替换</label>
        <select id="shape-replacement" value={String(replacements[selected.id] ?? '')}
          onChange={(event) => onEdit({ kind: 'shape', id: selected.id, key: 'prototype', value: event.target.value })}>
          <option value="">保持原形</option>
          {Object.keys(prototypes).map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>}
    </section>}

    {grid && <section className="inspector-section" aria-label="矩阵结构参数">
      <h3>PARAMETRIC / 矩阵结构</h3>
      {GRID_SPECS.filter((item) => typeof grid[item.key] === 'number').map((item) =>
        <NumericControl key={item.key} spec={item} value={Number(grid[item.key])}
          onCommit={(next) => onEdit({ kind: 'grid', key: item.key, value: next })} />)}
      {Array.isArray(grid.basis_u_vector) && <p className="inspector-readonly">当前含斜向基向量；间距和旋转会同步调整基向量。</p>}
    </section>}

    {fields.length > 0 && <section className="inspector-section" aria-label="参数场">
      <h3>FIELD / 参数场</h3>
      <label className="field-picker">选择已有参数场
        <select value={String(activeField?.id ?? '')} onChange={(event) => setFieldId(event.target.value)}>
          {fields.map((field) => <option key={String(field.id)} value={String(field.id)}>
            {fieldLabel[String(field.type)] ?? String(field.type)} · {String(field.id)}
          </option>)}
        </select>
      </label>
      {activeField && (() => {
        const type = String(activeField.type)
        const parameters = asRecord(activeField.parameters) ?? {}
        if (type === 'composite') return <p className="inspector-readonly">组合场只读：A={String(parameters.input_a_field_id ?? '—')}，B={String(parameters.input_b_field_id ?? '—')}，运算={String(parameters.operator ?? '—')}。原始引用完整保留。</p>
        if (type === 'image' || !FIELD_SPECS[type]) return <p className="inspector-readonly">该参数场当前只读；图片资产尚未接入网页。</p>
        return <>
          {FIELD_SPECS[type].filter((item) => typeof parameters[item.key] === 'number').map((item) =>
            <NumericControl key={`${activeField.id}-${item.key}`} spec={item} value={Number(parameters[item.key])}
              onCommit={(next) => onEdit({ kind: 'field', id: String(activeField.id), key: item.key, value: next })} />)}
          {typeof parameters.invert === 'boolean' && <label className="parameter-toggle">
            <input type="checkbox" checked={parameters.invert} onChange={(event) =>
              onEdit({ kind: 'field', id: String(activeField.id), key: 'invert', value: event.target.checked })} />反转
          </label>}
        </>
      })()}
    </section>}

    {(scalarModifiers(dto).length > 0 || stackModifiers(dto).length > 0) &&
      <section className="inspector-section" aria-label="效果堆栈">
        <h3>MODIFIERS / 效果堆栈</h3>
        {scalarModifiers(dto).map((modifier) => {
          const id = String(modifier.id)
          const type = String(modifier.type)
          const mapping = asRecord(modifier.mapping) ?? {}
          return <div className="modifier-card" key={`scalar-${id}`}>
            <label className="parameter-toggle"><input type="checkbox" checked={modifier.enabled !== false}
              onChange={(event) => onEdit({ kind: 'scalar', id, key: 'enabled', value: event.target.checked })} />
              {modifierLabel[type] ?? type} · {id}</label>
            <small>Field: {String(modifier.field_id ?? '—')}</small>
            {(type === 'size' || type === 'rotation') && MAPPING_SPECS.filter((item) => typeof mapping[item.key] === 'number').map((item) =>
              <NumericControl key={item.key} spec={item} value={Number(mapping[item.key])}
                onCommit={(next) => onEdit({ kind: 'scalar', id, key: item.key, value: next })} />)}
            {type === 'density' && typeof modifier.threshold === 'number' &&
              <NumericControl spec={{ key: 'threshold', label: '阈值', min: 0, max: 1, step: 0.01 }}
                value={modifier.threshold} onCommit={(next) => onEdit({ kind: 'scalar', id, key: 'threshold', value: next })} />}
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
            {type === 'position' ? POSITION_SPECS.filter((item) => typeof parameters[item.key] === 'number').map((item) =>
              <NumericControl key={item.key} spec={item} value={Number(parameters[item.key])}
                onCommit={(next) => onEdit({ kind: 'stack', id, key: item.key, value: next })} />)
              : <small>此有序层可启用/停用；详细参数暂由桌面版编辑。</small>}
          </div>
        })}
      </section>}
  </fieldset>
}
