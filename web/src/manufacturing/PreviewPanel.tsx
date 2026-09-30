import { useEffect, useRef, useState } from 'react'
import type { ManufacturingBuildResult } from '../api/manufacturing'
import { fetchStl, stlFileName } from '../api/manufacturingArtifacts'
import type { ManufacturingStatus } from './useManufacturing'
import { ThreePreview } from './ThreePreview'

interface Props {
  result: ManufacturingBuildResult | null
  status: ManufacturingStatus
  projectName: string | null
  isCurrentResult: (resultId: string) => boolean
}

export function PreviewPanel({ result, status, projectName, isCurrentResult }: Props) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const resultId = result?.manufacturing_result_id ?? null
  useEffect(() => () => controller.current?.abort(), [resultId])

  const download = async () => {
    if (!resultId || !isCurrentResult(resultId)) return
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    setDownloading(true)
    setDownloadError(null)
    try {
      const blob = await fetchStl(resultId, next.signal)
      if (next.signal.aborted || !isCurrentResult(resultId)) return
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = stlFileName(projectName)
      document.body.append(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (error) {
      if (!next.signal.aborted && isCurrentResult(resultId)) {
        setDownloadError(error instanceof Error ? error.message : 'STL 下载失败。')
      }
    } finally {
      if (!next.signal.aborted) setDownloading(false)
    }
  }

  if (!result) return <section className="preview-empty" aria-label="三维预览未就绪">
    <h1>3D 模型</h1>
    <p>{status === 'stale' ? '设计或厚度已变化，旧预览与 STL 已失效。请返回制造模式重新检查并生成。'
      : '请先在制造模式点击「检查并生成」，再查看最终模型和下载 STL。'}</p>
    <button type="button" disabled>下载 STL</button>
  </section>

  return <section className="preview-panel" aria-label="最终模型与导出">
    <div className="preview-header"><div><span className="eyebrow">VALIDATED MANUFACTURING RESULT</span><h1>3D 模型</h1>
      <p>XYZ：{result.bounds_mm?.size_x.toFixed(2)} × {result.bounds_mm?.size_y.toFixed(2)} × {result.bounds_mm?.size_z.toFixed(2)} mm
        {' · '}组件：{result.component_count}</p></div>
      <button type="button" onClick={() => void download()} disabled={downloading}>
        {downloading ? '正在下载…' : '下载 STL'}</button></div>
    <ThreePreview key={result.manufacturing_result_id} resultId={result.manufacturing_result_id} />
    {downloadError && <p className="manufacturing-error" role="alert">{downloadError}</p>}
    <small className="manufacturing-result-id">预览与 STL 共用结果编号：{resultId}</small>
  </section>
}
