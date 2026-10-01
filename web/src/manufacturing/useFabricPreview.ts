import { useCallback, useEffect, useRef, useState } from 'react'
import { requestFabricPreview, type FabricDesignPreview } from '../api/fabricPreview'
import type { PatternDocumentDTO } from '../model/types'

type State = { key: string | null; status: 'idle' | 'building' | 'ready' | 'error';
  result: FabricDesignPreview | null; error: string | null }

export function useFabricPreview(dto: PatternDocumentDTO | null) {
  const key = dto ? `${dto.document_id}:${dto.document_revision}` : null
  const currentKey = useRef(key)
  currentKey.current = key
  const abort = useRef<AbortController | null>(null)
  const requestSequence = useRef(0)
  const [state, setState] = useState<State>({ key: null, status: 'idle', result: null, error: null })
  useEffect(() => { abort.current?.abort(); ++requestSequence.current }, [key])
  useEffect(() => () => { abort.current?.abort(); ++requestSequence.current }, [])
  const status: State['status'] | 'stale' = state.key && state.key !== key ? 'stale' : state.status
  const result = status === 'ready' ? state.result : null
  const update = useCallback(async () => {
    if (!dto || !key) return
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    const sequence = ++requestSequence.current
    setState({ key, status: 'building', result: null, error: null })
    try {
      const result = await requestFabricPreview(dto, controller.signal)
      if (!controller.signal.aborted && sequence === requestSequence.current && currentKey.current === key)
        setState({ key, status: 'ready', result, error: null })
    } catch (error) {
      if (!controller.signal.aborted && sequence === requestSequence.current && currentKey.current === key)
        setState({ key, status: 'error', result: null, error: error instanceof Error ? error.message : '预览失败。' })
    }
  }, [dto, key])
  return { status, result, error: status === 'stale' ? null : state.error, update }
}
