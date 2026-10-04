import { useEffect, useRef, useState } from 'react'
import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { formatMm } from '../model/formatMm'
import { realSizeConfirmed } from '../document/realSize'

export function RealSizePanel({ document, bounds, disabled, onConfirm }: {
  document: PatternDocumentDTO | null
  bounds: BoundsMM | null
  disabled: boolean
  onConfirm: (widthMm: number, heightMm: number) => void
}) {
  const [widthText, setWidthText] = useState('')
  const [heightText, setHeightText] = useState('')
  const [source, setSource] = useState<'width' | 'height'>('width')
  const [error, setError] = useState<string | null>(null)
  const submitted = useRef<{ width: number; height: number } | null>(null)
  useEffect(() => {
    if (!bounds) return
    if (submitted.current && Math.abs(submitted.current.width - bounds.width) < 0.001 &&
        Math.abs(submitted.current.height - bounds.height) < 0.001) {
      submitted.current = null
      return
    }
    setWidthText(formatMm(bounds.width))
    setHeightText(formatMm(bounds.height))
    setError(null)
  }, [document?.document_id, document?.document_revision, bounds?.width, bounds?.height])
  const change = (axis: 'width' | 'height', text: string) => {
    setSource(axis)
    setError(null)
    if (axis === 'width') setWidthText(text)
    else setHeightText(text)
    const value = Number(text)
    if (!bounds || !text.trim() || !Number.isFinite(value) || value <= 0) return
    if (axis === 'width') setHeightText(formatMm(value * bounds.height / bounds.width))
    else setWidthText(formatMm(value * bounds.width / bounds.height))
  }
  const confirm = () => {
    if (!bounds) return
    const requested = Number(source === 'width' ? widthText : heightText)
    if (!Number.isFinite(requested) || requested <= 0 || !(source === 'width' ? widthText : heightText).trim()) {
      setError('宽度和高度必须大于 0 mm。')
      return
    }
    const width = source === 'width' ? requested : requested * bounds.width / bounds.height
    const height = source === 'height' ? requested : requested * bounds.height / bounds.width
    submitted.current = { width, height }
    onConfirm(width, height)
  }
  return <section className="real-size-panel" aria-label="真实尺寸">
    <h2>真实尺寸</h2>
    <p>当前尺寸：{bounds ? `${formatMm(bounds.width)} × ${formatMm(bounds.height)} mm` : '待计算'} ·
      <strong>{document && realSizeConfirmed(document, bounds) ? '已确认' : '未确认'}</strong></p>
    <div className="real-size-inputs">
      <label>宽度 mm<input aria-label="真实宽度 mm" type="number" min="0.000001" step="any" value={widthText}
        disabled={disabled || !bounds} onChange={(event) => change('width', event.target.value)} /></label>
      <label>高度 mm<input aria-label="真实高度 mm" type="number" min="0.000001" step="any" value={heightText}
        disabled={disabled || !bounds} onChange={(event) => change('height', event.target.value)} /></label>
    </div>
    <label className="real-size-lock"><input type="checkbox" checked readOnly disabled />锁定比例</label>
    <small>当前文档使用统一毫米映射，暂只支持等比调整。</small>
    <button type="button" disabled={disabled || !bounds} onClick={confirm}>确认尺寸</button>
    {error && <p role="alert">{error}</p>}
  </section>
}
