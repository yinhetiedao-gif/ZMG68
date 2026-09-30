import { useId } from 'react'
import type { ParameterDefinition, ParameterGroup, ParameterValue } from './parameterSchema'
import { sliderBounds, validateParameter } from './parameterSchema'
import { useParameterDraft } from './ParameterInteraction'

function ParameterInput({ definition, value, onCommit }: {
  definition: ParameterDefinition; value: ParameterValue; onCommit: (value: ParameterValue) => void
}) {
  const id = useId()
  const { draft, pending, change, cancel, submit, commitNumber: commit } = useParameterDraft(value, onCommit,
    (next) => validateParameter(definition, next))
  const reset = <button type="button" className="parameter-reset" aria-label={`重置${definition.label}`}
    title={`恢复默认值：${definition.default}${definition.unit ? ` ${definition.unit}` : ''}`}
    disabled={value === definition.default && !pending}
    onPointerDown={(event) => event.preventDefault()} onClick={() => submit(definition.default)}>重置</button>
  if (definition.type === 'boolean') return <div className="parameter-control parameter-boolean">
    <label className="parameter-toggle" title={definition.description}>
      <input type="checkbox" checked={value === true} onChange={(event) => submit(event.target.checked)} />{definition.label}
    </label>{reset}
  </div>
  if (definition.type === 'select') return <div className="parameter-control">
    <div className="parameter-heading"><label htmlFor={id}>{definition.label}</label>{reset}</div>
    <select id={id} value={String(value)} onChange={(event) => {
      submit(event.target.value)
    }}>{definition.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
  </div>
  const min = definition.min ?? undefined
  const max = definition.max ?? undefined
  const step = definition.step ?? 'any'
  const slider = min !== undefined && max !== undefined
    ? sliderBounds(min, max, definition.unit) : null
  return <div className="parameter-control" title={definition.description}>
    <div className="parameter-heading"><label htmlFor={id}>{definition.label}{definition.unit ? ` (${definition.unit})` : ''}</label>{reset}</div>
    <div className="parameter-inputs">
      {slider && <input type="range" aria-label={`${definition.label}滑杆`}
        min={slider.min} max={slider.max} step={step} value={draft.trim() && Number.isFinite(Number(draft))
          ? Math.min(slider.max, Math.max(slider.min, Number(draft)))
          : Math.min(slider.max, Math.max(slider.min, Number(value)))}
        onChange={(event) => change(event.target.value)} onPointerUp={commit} onKeyUp={commit} onBlur={commit}
        onPointerCancel={cancel} />}
      <input id={id} type="number" min={min} max={max} step={step} value={draft}
        onChange={(event) => change(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
          if (event.key === 'Escape') cancel()
        }} onBlur={commit} />
    </div>
    {pending && <small className="parameter-pending">待提交 · 松开滑杆或确认数值</small>}
  </div>
}

export function ParameterPanel({ group, values, onCommit }: {
  group: ParameterGroup
  values: Record<string, unknown>
  onCommit: (key: string, value: ParameterValue) => void
}) {
  return <>{group.parameters.filter((definition) => definition.id in values &&
    validateParameter(definition, definition.type === 'select'
      ? String(values[definition.id]) : values[definition.id] as ParameterValue)).map((definition) =>
    <ParameterInput key={definition.id} definition={definition}
      value={definition.type === 'select' ? String(values[definition.id]) : values[definition.id] as ParameterValue}
      onCommit={(value) => onCommit(definition.id, value)} />)}</>
}
