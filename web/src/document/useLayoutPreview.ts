import { useEffect, useRef, useState } from 'react'
import { evaluateDocument } from '../api/evaluate'
import type { EvaluateResponse, PatternDocumentDTO } from '../model/types'
import type { LayoutDraft } from './layoutDraft'

/** Display-only, Python-evaluated proposal. One active request, latest input only. */
export function useLayoutPreview(draft: LayoutDraft | null, enabled: boolean, fetcher: typeof fetch,
  seed: { key: string; result: EvaluateResponse } | null) {
  return useDocumentPreview(enabled ? draft?.proposal ?? null : null, fetcher, seed)
}

export function useDocumentPreview(dto: PatternDocumentDTO | null, fetcher: typeof fetch,
  seed: { key: string; result: EvaluateResponse } | null = null, session = dto?.document_id ?? '') {
  const key = dto ? JSON.stringify(dto) : null
  const latest = useRef(key); latest.current = key
  const active = useRef(false)
  const pendingSince = useRef<number | null>(null)
  const mounted = useRef(true)
  const [drained, setDrained] = useState(0)
  const [state, setState] = useState<{ key: string | null; result: EvaluateResponse | null; error: string | null;
    lastResult: EvaluateResponse | null; session: string }>({ key: null, result: null, error: null, lastResult: null, session: '' })
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; latest.current = null } }, [])
  useEffect(() => {
    if (!dto || !key || seed?.key === key || state.key === key) { pendingSince.current = null; return }
    // Bounded wait, rather than resetting a debounce on every pointermove.
    // There is still only one in-flight request and one latest pending input.
    pendingSince.current ??= Date.now()
    if (active.current) return
    const timer = setTimeout(() => {
      if (latest.current !== key || active.current) return
      active.current = true
      pendingSince.current = null
      void evaluateDocument(dto, undefined, fetcher).then(result => {
        if (mounted.current && latest.current === key) setState({ key, result, error: null, lastResult: result, session })
      }).catch((error: unknown) => {
        if (mounted.current && latest.current === key) setState(previous => ({ ...previous, key, result: null,
          error: error instanceof Error ? error.message : '候选预览失败。' }))
      }).finally(() => { active.current = false; if (mounted.current) setDrained(value => value + 1) })
    }, Math.max(0, 180 - (Date.now() - pendingSince.current)))
    return () => clearTimeout(timer)
  }, [dto, key, fetcher, seed, state.key, drained, session])
  const result = seed?.key === key ? seed.result : state.key === key ? state.result : null
  const retry = () => {
    // Explicit failure recovery only. Never cancel/release a running backend slot.
    if (!key || latest.current !== key || active.current || state.key !== key || !state.error) return
    pendingSince.current = null
    setState(previous => ({ ...previous, key: null, result: null, error: null }))
  }
  return { result, displayResult: result ?? (session && state.session === session ? state.lastResult : null),
    pending: Boolean(key && !result && state.key !== key), error: key === state.key ? state.error : null, retry }
}
