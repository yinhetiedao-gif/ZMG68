import { useEffect, useRef, useState } from 'react'
import { requestFabricCandidate, type FabricCandidateReport } from '../api/fabricCandidate'
import type { PatternDocumentDTO } from '../model/types'

export function FabricPreflightPanel({ document, fetcher = fetch, disabled = false, computeBusy = false, isComputeBusy, canUseInputs }: {
  document: PatternDocumentDTO; fetcher?: typeof fetch; disabled?: boolean; computeBusy?: boolean; isComputeBusy?: () => boolean
  canUseInputs?: () => boolean
}) {
  const key = JSON.stringify(document)
  const current = useRef(key); current.current = key
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const [state, setState] = useState<{ key: string; building: boolean;
    result: FabricCandidateReport | null; error: string | null } | null>(null)
  useEffect(() => { controller.current?.abort(); ++sequence.current }, [key])
  useEffect(() => () => { controller.current?.abort(); ++sequence.current }, [])
  const stale = state !== null && state.key !== key
  const result = stale ? null : state?.result
  async function check() {
    if (disabled || computeBusy || isComputeBusy?.() || canUseInputs && !canUseInputs()) return
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    const request = ++sequence.current
    setState({ key, building: true, result: null, error: null })
    try {
      const result = await requestFabricCandidate(document, abort.signal, fetcher)
      if (!abort.signal.aborted && current.current === key && request === sequence.current)
        setState({ key, building: false, result, error: null })
    } catch (error) {
      if (!abort.signal.aborted && current.current === key && request === sequence.current)
        setState({ key, building: false, result: null, error: error instanceof Error ? error.message : '检查失败。' })
    }
  }
  return <section className="manufacturing-report" aria-label="Fabric 可制造性预检">
    <h2>可制造性预检</h2>
    <p>这是独立候选检查；仅图案单元不要求底布连接，带基底检查实际接触。最终网格仍须严格校验。</p>
    <button type="button" className="ui-secondary" disabled={disabled || computeBusy || !stale && state?.building === true}
      onClick={() => void check()}>检查可制造性</button>
    <p role="status">{stale ? '设计已变化，请重新检查可制造性。' : state?.building ? '正在检查可制造性…' : result ? '预检完成（未融合）' : state?.error ? '独立预检失败' : '独立预检尚未运行'}</p>
    {!stale && state?.error && <p role="alert">{state.error}</p>}
    {result && <>
      {result.output_mode === 'cells_only' ? <p>实例：{result.enabled_instance_count} / {result.instance_count} · 有效单元：{result.attachment_counts.VALID} · 无效：{result.attachment_counts.INVALID} · 无基底，不检查底布连接</p> : <p>实例：{result.enabled_instance_count} / {result.instance_count} · 接触到底布：{result.attachment_counts.ATTACHED}
        {' '}· 边缘接触：{result.attachment_counts.MARGINAL} · 未连接：{result.attachment_counts.DETACHED} · 无效：{result.attachment_counts.INVALID}</p>
      }
      {result.bounds_mm && <p>XYZ：{result.bounds_mm[1].map((v, i) => (v - result.bounds_mm![0][i]).toFixed(2)).join(' × ')} mm</p>}
      {result.issues.map((issue, index) => <p key={index}>{issue.level} · {issue.message}</p>)}
      <details><summary>单元诊断（{result.attachments.filter(item => !['ATTACHED','VALID'].includes(item.status)).length} 个需关注）</summary>
        {result.attachments.filter(item => !['ATTACHED','VALID'].includes(item.status)).map(item => <p key={item.instance_id}>
          {item.instance_id} · {item.status} · 接触面积 {item.contact_area_mm2.toPrecision(4)} mm²
          {' '}· {item.issues.map(issue => issue.message).join('；')}</p>)}
      </details>
    </>}
  </section>
}
