import { useCallback, useEffect, useRef, useState } from 'react'
import { requestFabricPreview, type FabricDesignPreview } from '../api/fabricPreview'
import { HttpRequestError } from '../api/requestErrors'
import type { PatternDocumentDTO } from '../model/types'

type State = { key: string | null; status: 'idle' | 'building' | 'ready' | 'error';
  result: FabricDesignPreview | null; document: PatternDocumentDTO | null; error: string | null; errorCode: string | null }

export function useFabricPreview(dto: PatternDocumentDTO | null, fetcher: typeof fetch = fetch,
  isComputeBusy?: () => boolean, options?: { automatic: boolean; blocked: boolean; computeBusy: boolean }) {
  const key = dto ? JSON.stringify(dto) : null
  const currentKey = useRef(key)
  currentKey.current = key
  const abort = useRef<AbortController | null>(null)
  const requestSequence = useRef(0)
  const [state, setState] = useState<State>({ key: null, status: 'idle', result: null, document: null, error: null, errorCode: null })
  const active = useRef<symbol | null>(null)
  const [drained, setDrained] = useState(0)
  useEffect(() => { abort.current?.abort(); ++requestSequence.current }, [key])
  useEffect(() => () => { abort.current?.abort(); ++requestSequence.current }, [])
  const status: State['status'] | 'stale' = state.key && state.key !== key ? 'stale' : state.status
  const result = status === 'ready' ? state.result : null
  const update = useCallback(async () => {
    if (active.current || isComputeBusy?.() || options?.blocked) return
    if (!dto || !key) return
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    const sequence = ++requestSequence.current
    const token = Symbol('preview'); active.current = token
    setState(previous => ({ ...previous, key, status: 'building', error: null, errorCode: null }))
    try {
      const result = await requestFabricPreview(dto, controller.signal, fetcher)
      if (!controller.signal.aborted && sequence === requestSequence.current && currentKey.current === key)
        setState({ key, status: 'ready', result, document: dto, error: null, errorCode: null })
    } catch (error) {
      if (!controller.signal.aborted && sequence === requestSequence.current && currentKey.current === key)
        setState(previous => ({ ...previous, key, status: 'error', error: error instanceof Error ? error.message : '预览失败。',
          errorCode: error instanceof HttpRequestError ? error.code : null }))
    } finally {
      if (active.current === token) { active.current = null; setDrained(value => value + 1) }
    }
  }, [dto, key, fetcher, isComputeBusy, options?.blocked])
  useEffect(() => {
    if (!options?.automatic || options.blocked || options.computeBusy || active.current
      || !dto || !key || state.key === key && ['ready', 'error'].includes(state.status)) return
    const timer = window.setTimeout(() => void update(), 180)
    return () => window.clearTimeout(timer)
  }, [key, dto, state.key, state.status, update, options?.automatic, options?.blocked, options?.computeBusy, drained])
  const displayResult = state.document?.document_id === dto?.document_id ? state.result : null
  return { status, result, displayResult, displayDocument: displayResult ? state.document : null,
    serverBusy: status === 'error' && state.errorCode === 'staging_busy',
    waitingForTask: Boolean(key && state.key !== key && (active.current || options?.computeBusy)),
    error: status === 'stale' ? null : state.error, update }
}
