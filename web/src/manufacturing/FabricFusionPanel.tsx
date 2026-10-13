import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { requestFabricFusion, fetchFabricStl, FabricRequestError, type FabricFinalReport } from '../api/fabricFusion'
import type { PatternDocumentDTO } from '../model/types'
import { fabricExportNotice } from './fabricCopy'

const stageLabels: Record<string, string> = { request: '请求', response_contract: '响应校验',
  candidate: '制造候选生成', preflight: '可制造性预检', backend: '融合服务',
  boolean_input: '融合输入检查', boolean_union: '实体融合', connectivity: '连通性检查',
  mesh_validation: '最终网格检查', bounds: '尺寸检查', stl_export: 'STL 导出', stl_roundtrip: 'STL 读回检查' }

export function FabricFusionPanel({ document, fetcher = fetch, disabled = false, testExportEnabled, computeBusy = false, isComputeBusy, actionHost, canUseInputs }: {
  document: PatternDocumentDTO; fetcher?: typeof fetch; disabled?: boolean; testExportEnabled?: boolean
  computeBusy?: boolean; isComputeBusy?: () => boolean
  actionHost?: HTMLElement | null
  canUseInputs?: () => boolean
}) {
  const key = useMemo(() => JSON.stringify(document), [document])
  const current = useRef(key); current.current = key
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const downloadController = useRef<AbortController | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const exportBlocked = useRef(disabled); exportBlocked.current = disabled
  const [state, setState] = useState<{ key: string; building: boolean;
    report: FabricFinalReport | null; error: string | null; diagnostics?: Record<string, unknown>;
    expired?: boolean } | null>(null)
  useEffect(() => { controller.current?.abort(); downloadController.current?.abort();
    setDownloading(false); setDownloadError(null); ++sequence.current }, [key])
  useEffect(() => () => { controller.current?.abort(); downloadController.current?.abort(); ++sequence.current }, [])
  const stale = state !== null && (state.key !== key || state.expired === true)
  const report = stale ? null : state?.report
  const exportEnabled = report ? report.export_available : testExportEnabled
  const statusText = stale ? '结果已失效，请重新生成。' : state?.building ? '正在生成最终制造网格……'
    : state?.error ? state.diagnostics?.error_code === 'staging_busy' ? '计算服务忙碌，请等待后再操作。' : '最终制造网格生成失败。' : report
      ? report.export_available ? '最终网格已通过检查' : '网格已通过检查，当前环境未启用测试导出。'
      : '请先生成最终制造网格。'
  async function build() {
    if (disabled || computeBusy || isComputeBusy?.() || canUseInputs && !canUseInputs()) return
    downloadController.current?.abort(); setDownloading(false); setDownloadError(null)
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
        setState({ key, building: false, report: null, error: error instanceof Error ? error.message : '生成失败。',
          diagnostics: error instanceof FabricRequestError ? error.diagnostics : undefined,
          expired: error instanceof FabricRequestError && error.expired })
    }
  }
  async function download() {
    if (disabled || canUseInputs && !canUseInputs() || !report || stale || !report.export_available || state?.building) return
    downloadController.current?.abort()
    const abort = new AbortController(); downloadController.current = abort
    const request = sequence.current
    setDownloading(true); setDownloadError(null)
    try {
      const blob = await fetchFabricStl(report, document, abort.signal, fetcher)
      if (abort.signal.aborted || exportBlocked.current || canUseInputs && !canUseInputs() || current.current !== key || sequence.current !== request) return
      const url = URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url; anchor.download = 'xiaomang-fabric.stl'
      window.document.body.append(anchor); anchor.click(); anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (error) {
      if (!abort.signal.aborted && current.current === key && sequence.current === request) {
        if (error instanceof FabricRequestError && error.expired) {
          setState({ key, building: false, report: null, error: null, expired: true, diagnostics: error.diagnostics })
          setDownloadError(null)
        } else if (error instanceof FabricRequestError && error.exportDisabled) {
          setState({ key, building: false, report: { ...report, export_available: false, stl_export_mode: 'disabled' }, error: null })
          setDownloadError(null)
        } else setDownloadError(error instanceof Error ? error.message : 'STL 导出失败。')
      }
    } finally { if (!abort.signal.aborted) setDownloading(false) }
  }
  const buildButton = <button type="button" className="ui-primary" disabled={disabled || computeBusy || !stale && state?.building === true}
    onClick={() => void build()}>{actionHost ? '生成最终模型' : '生成最终制造网格'}</button>
  const downloadButton = <button type="button" className="ui-primary" disabled={!report?.export_available || stale || downloading || disabled}
    onClick={() => void download()}>{downloading ? '正在导出…' : '下载测试 Fabric STL'}</button>
  return <section className="manufacturing-report" aria-label="Fabric 最终制造网格">
    <h2>最终制造网格</h2>
    <p>预检 → 实体融合 → 网格检查。{fabricExportNotice(exportEnabled)}</p>
    {!actionHost && buildButton}
    <p role="status">{statusText}</p>
    {stale && state?.report && <div aria-label="上次制造结果">
      <p>上次结果 · 已失效 · 结果 revision {state.report.document_revision} / 当前正式 revision {document.document_revision}</p>
      <p>上次组件：{state.report.connected_component_count} · 上次 XYZ：{state.report.bounds_mm[1].map((v,i)=>(v-state.report!.bounds_mm[0][i]).toFixed(2)).join(' × ')} mm（不可作为当前 STL 尺寸）</p>
    </div>}
    {!stale && state?.error && <p role="alert">Fabric STL 不可导出：
      {stageLabels[String(state.diagnostics?.stage)] ?? '生成'}阶段 · {state.error}</p>}
    {!stale && state?.diagnostics != null && <details><summary>诊断详情</summary>
      <pre>{JSON.stringify(state.diagnostics, null, 2)}</pre></details>}
    {report && <>
      <p>结果 revision {report.document_revision} / 当前正式 revision {document.document_revision}</p>
      <p>Components: {report.connected_component_count} · Watertight: Yes</p>
      {report.output_mode === 'cells_only' && <p>仅图案单元，无实体基底。{report.connected_component_count > 1 ? '包含多个独立封闭实体，不是融合为一体的面料。' : '实际校验为一个实体。'}</p>}
      <p>XYZ：{report.bounds_mm[1].map((v,i)=>(v-report.bounds_mm[0][i]).toFixed(2)).join(' × ')} mm</p>
      <p>制造接口重叠：{report.interface_overlap_mm} mm{report.cache_hit ? ' · 已复用融合结果' : ''}</p>
    </>}
    {actionHost ? createPortal(<div className="manufacturing-output-actions">{buildButton}{downloadButton}</div>, actionHost) : downloadButton}
    {downloadError && <p role="alert">{downloadError}</p>}
  </section>
}
