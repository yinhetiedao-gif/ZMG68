import { createContext, useContext, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ParameterValue } from './parameterSchema'

// Browser-only draft bookkeeping. Neither pending state nor control identity
// belongs in PatternDocument or its Undo history.
export const ParameterInteraction = createContext<{
  syncToken: string
  onPending?: (id: string, pending: boolean) => void
}>({ syncToken: '' })

export function useParameterDraft(value: ParameterValue, onCommit: (value: ParameterValue) => void,
  validate: (value: ParameterValue) => boolean, onDraft?: (value: ParameterValue | null) => void) {
  const { syncToken, onPending } = useContext(ParameterInteraction)
  const id = useId()
  const [draft, setDraft] = useState(String(value))
  const draftRef = useRef(String(value))
  const committedRef = useRef(value)
  const draftCallback = useRef(onDraft); draftCallback.current = onDraft
  const change = (next: string) => {
    draftRef.current = next; setDraft(next)
    onPending?.(id, next !== String(value))
    const candidate = typeof value === 'number' ? next.trim() === '' ? NaN : Number(next) : next
    onDraft?.(next !== String(value) && validate(candidate) ? candidate : null)
  }
  useLayoutEffect(() => {
    draftRef.current = String(value)
    committedRef.current = value
    setDraft(String(value))
    draftCallback.current?.(null)
    onPending?.(id, false)
  }, [value, syncToken])
  useEffect(() => () => draftCallback.current?.(null), [])
  const pending = draft !== String(value)
  useEffect(() => {
    onPending?.(id, pending)
    return () => onPending?.(id, false)
  }, [id, pending, onPending])
  const cancel = () => change(String(value))
  const submit = (next: ParameterValue) => {
    if (!validate(next)) { cancel(); return }
    if (next !== committedRef.current) {
      committedRef.current = next
      onCommit(next)
    }
    change(String(next))
    onPending?.(id, false)
    onDraft?.(null)
  }
  const commitNumber = () => submit(draftRef.current.trim() === '' ? NaN : Number(draftRef.current))
  return { draft, pending, change, cancel, submit, commitNumber }
}
