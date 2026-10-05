import { useEffect, useRef, useState } from 'react'
import { requestFabricFusion, type FabricFinalReport } from '../api/fabricFusion'
import type { PatternDocumentDTO } from '../model/types'

export function FabricFusionPanel({ document, fetcher = fetch, disabled = false }: {
  document: PatternDocumentDTO; fetcher?: typeof fetch; disabled?: boolean
}) {
  const key = `${document.document_id}:${document.document_revision}`
  const current = useRef(key); current.current = key
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const [state, setState] = useState<{ key: string; building: boolean;
    report: FabricFinalReport | null; error: string | null } | null>(null)
  useEffect(() => { controller.current?.abort(); ++sequence.current }, [key])
  useEffect(() => () => { controller.current?.abort(); ++sequence.current }, [])
  const stale = state !== null && state.key !== key
  const report = stale ? null : state?.report
  async function build() {
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    const request = ++sequence.current
    setState({ key, building: true, report: null, error: null })
    try {
      const report = await requestFabricFusion(document, abort.signal, fetcher)
      if (!abort.signal.aborted && current.current === key && request === sequence.current)
        setState({ key, building: false, report, error: null })
    } catch (error) {
      if (!abort.signal.aborted && current.current === key && request === sequence.current)
        setState({ key, building: false, report: null, error: error instanceof Error ? error.message : '生成失败。' })
    }
  }
  return <section className="manufacturing-report" aria-label="Fabric 最终制造网格">
    <h2>最终制造网格</h2>
    <p>预检 → 实体融合 → 网格检查。Fabric STL 尚未开放。</p>
    <button type="button" className="ui-secondary" disabled={disabled || !stale && state?.building === true}
      onClick={() => void build()}>生成最终制造网格</button>
    <p role="status">{stale ? '设计已变化，请重新生成最终制造网格。' : state?.building ? '正在融合并检查最终网格…' :
      report ? '最终网格已通过检查' : '尚未生成最终网格'}</p>
    {!stale && state?.error && <p role="alert">{state.error}</p>}
    {report && <>
      <p>Components: {report.connected_component_count} · Watertight: Yes</p>
      <p>XYZ：{report.bounds_mm[1].map((v,i)=>(v-report.bounds_mm[0][i]).toFixed(2)).join(' × ')} mm</p>
      <p>制造接口重叠：{report.interface_overlap_mm} mm{report.cache_hit ? ' · 已复用融合结果' : ''}</p>
    </>}
  </section>
}
