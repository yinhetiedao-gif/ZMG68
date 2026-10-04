import { useEffect, useRef, useState } from 'react'
import type { ManufacturingBuildResult } from '../api/manufacturing'
import { fetchStl, stlFileName } from '../api/manufacturingArtifacts'
import type { ManufacturingStatus } from './useManufacturing'

interface Props {
  result: ManufacturingBuildResult | null
  status: ManufacturingStatus
  projectName: string | null
  isCurrentResult: (resultId: string) => boolean
  label?: string
}

export function StlExportButton({ result, status, projectName, isCurrentResult, label = '导出 STL' }: Props) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const resultId = result?.manufacturing_result_id ?? null
  const validMesh = result?.mesh_validation_summary?.error_count === 0
  const enabled = Boolean(resultId && (status === 'ready' || status === 'warning') && validMesh
    && isCurrentResult(resultId))
  const reason = status === 'stale' ? '设计或厚度已修改，请重新检查并生成。'
    : status === 'building' ? '正在生成制造模型，请稍候。'
      : status === 'error' ? '制造检查失败，请修正后重新生成。'
        : !resultId ? '请先检查并生成制造模型。'
          : !validMesh ? 'Mesh 检查存在错误，无法导出 STL。'
            : !enabled ? '制造结果已失效，请重新检查并生成。' : null

  useEffect(() => {
    setDownloading(false)
    setDownloadError(null)
    return () => controller.current?.abort()
  }, [resultId])

  const download = async () => {
    if (!resultId || !enabled) return
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
        setDownloadError(error instanceof Error ? error.message : 'STL 导出失败。')
      }
    } finally {
      if (!next.signal.aborted) setDownloading(false)
    }
  }

  return <div className="stl-export-action">
    <button type="button" className="ui-primary" onClick={() => void download()} disabled={!enabled || downloading}>
      {downloading ? '正在导出…' : label}
    </button>
    {reason && <small className="stl-export-reason">{reason}</small>}
    {downloadError && <p className="manufacturing-error" role="alert">{downloadError}</p>}
  </div>
}
