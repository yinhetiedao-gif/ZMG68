import { useEffect, useId, useRef, useState } from 'react'
import type { ParameterDefinition, ParameterGroup, ParameterValue } from './parameterSchema'
import { validateParameter } from './parameterSchema'

function ParameterInput({ definition, value, onCommit }: {
  definition: ParameterDefinition; value: ParameterValue; onCommit: (value: ParameterValue) => void
}) {
  const id = useId()
  const [draft, setDraft] = useState(String(value))
  const draftRef = useRef(String(value))
  const committedRef = useRef(value)
  useEffect(() => {
    setDraft(String(value)); draftRef.current = String(value); committedRef.current = value
  }, [value])
  const change = (next: string) => { draftRef.current = next; setDraft(next) }
  const commit = () => {
    const raw = draftRef.current
    const next = raw.trim() === '' ? NaN : Number(raw)
    if (!validateParameter(definition, next)) { change(String(value)); return }
    if (next !== committedRef.current) { committedRef.current = next; onCommit(next) }
  }
  if (definition.type === 'boolean') return <label className="parameter-toggle" title={definition.description}>
    <input type="checkbox" checked={value === true} onChange={(event) => onCommit(event.target.checked)} />{definition.label}
  </label>
  if (definition.type === 'select') return <div className="parameter-control">
    <label htmlFor={id}>{definition.label}</label>
    <select id={id} value={String(value)} onChange={(event) => {
      if (validateParameter(definition, event.target.value)) onCommit(event.target.value)
    }}>{definition.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
  </div>
  const min = definition.min ?? undefined
  const max = definition.max ?? undefined
  const step = definition.step ?? 'any'
  return <div className="parameter-control" title={definition.description}>
    <label htmlFor={id}>{definition.label}{definition.unit ? ` (${definition.unit})` : ''}</label>
    <div className="parameter-inputs">
      {min !== undefined && max !== undefined && <input type="range" aria-label={`${definition.label}滑杆`}
        min={min} max={max} step={step} value={draft.trim() && Number.isFinite(Number(draft))
          ? Math.min(max, Math.max(min, Number(draft))) : Number(value)}
        onChange={(event) => change(event.target.value)} onPointerUp={commit} onKeyUp={commit} onBlur={commit} />}
      <input id={id} type="number" min={min} max={max} step={step} value={draft}
        onChange={(event) => change(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }} onBlur={commit} />
    </div>
  </div>
}

export function ParameterPanel({ group, values, onCommit }: {
  group: ParameterGroup
  values: Record<string, unknown>
  onCommit: (key: string, value: ParameterValue) => void
}) {
  return <>{group.parameters.filter((definition) => definition.id in values &&
    validateParameter(definition, values[definition.id] as ParameterValue)).map((definition) =>
    <ParameterInput key={definition.id} definition={definition}
      value={values[definition.id] as ParameterValue}
      onCommit={(value) => onCommit(definition.id, value)} />)}</>
}
