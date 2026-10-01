import { useCallback, useEffect, useRef, useState } from 'react'
import { buildManufacturing, type ManufacturingBuildResult } from '../api/manufacturing'
import type { PatternDocumentDTO } from '../model/types'
import { fabricBase } from '../document/fabricBase'

export type ManufacturingStatus = 'idle' | 'building' | 'ready' | 'warning' | 'error' | 'stale'
type BuildState = { key: string | null; status: ManufacturingStatus; result: ManufacturingBuildResult | null; error: string | null }

export function useManufacturing(dto: PatternDocumentDTO | null) {
  const [heightText, setHeightText] = useState('2.0')
  const [buildState, setBuildState] = useState<BuildState>({ key: null, status: 'idle', result: null, error: null })
  const controller = useRef<AbortController | null>(null)
  const requestSequence = useRef(0)
  const base = fabricBase(dto)
  const heightMm = base ? base.thickness_mm : Number(heightText)
  const validHeight = (base !== null || heightText.trim() !== '') && Number.isFinite(heightMm) && heightMm > 0
  const key = dto && validHeight ? `${dto.document_id}:${dto.document_revision}:${heightMm}` : null
  const keyRef = useRef(key)
  keyRef.current = key

  useEffect(() => {
    controller.current?.abort()
    ++requestSequence.current
  }, [key])
  useEffect(() => () => controller.current?.abort(), [])

  const status: ManufacturingStatus = buildState.key && buildState.key !== key ? 'stale' : buildState.status
  const result = (status === 'ready' || status === 'warning') && buildState.key === key ? buildState.result : null
  const activeResultRef = useRef(result)
  activeResultRef.current = result
  const isCurrentResult = useCallback((resultId: string) =>
    activeResultRef.current?.manufacturing_result_id === resultId && keyRef.current === buildState.key,
  [buildState.key])
  const build = useCallback(async () => {
    if (!dto || !key || !validHeight) {
      setBuildState({ key, status: 'error', result: null, error: '请先打开有效图案，并输入大于 0 mm 的厚度。' })
      return
    }
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    const sequence = ++requestSequence.current
    setBuildState({ key, status: 'building', result: null, error: null })
    try {
      const response = await buildManufacturing(dto, heightMm, next.signal)
      if (next.signal.aborted || sequence !== requestSequence.current || keyRef.current !== key) return
      const warning = response.component_count > 1 || response.warnings.length > 0
        || response.geometry_validation_summary.warning_count > 0
        || (response.mesh_validation_summary?.warning_count ?? 0) > 0
      setBuildState({ key, status: warning ? 'warning' : 'ready', result: response, error: null })
    } catch (error) {
      if (next.signal.aborted || sequence !== requestSequence.current || keyRef.current !== key) return
      setBuildState({ key, status: 'error', result: null, error: error instanceof Error ? error.message : '制造检查失败。' })
    }
  }, [dto, heightMm, key, validHeight])

  return { heightText: base ? String(base.thickness_mm) : heightText, setHeightText, validHeight, status, result, isCurrentResult,
    error: status === 'stale' ? null : buildState.error, build }
}
