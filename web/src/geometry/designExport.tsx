import { renderToStaticMarkup } from 'react-dom/server'
import { geometryShape } from './render'
import type { EvaluateResponse, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'

/** The same applied Python result and primitive/path renderer as Workspace2D.
 * Artboard clipping is export-only; it never changes STL/manufacturing bounds. */
export function designSvg(dto: PatternDocumentDTO, result: EvaluateResponse): string {
  const mm = millimetresPerUnit(dto.document), c = dto.document.canvas
  if (!mm || !result.geometry.length || result.document_id !== dto.document_id || result.document_revision !== dto.document_revision)
    throw new Error('当前已应用设计尚未求值完成，不能导出。')
  const x = (c.origin_x ?? 0) * mm, y = (c.origin_y ?? 0) * mm, width = c.width * mm, height = c.height * mm
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + renderToStaticMarkup(
    <svg xmlns="http://www.w3.org/2000/svg" version="1.1" width={`${width}mm`} height={`${height}mm`} viewBox={`${x} ${y} ${width} ${height}`}>
      <defs><clipPath id="artboard"><rect x={x} y={y} width={width} height={height} /></clipPath></defs>
      <g clipPath="url(#artboard)">{result.geometry.map(item => <g key={item.id} id={item.id}>{geometryShape(item, mm)}</g>)}</g>
    </svg>)
}
export async function designPng(svg: string, width: number, aspect: number): Promise<Blob> {
  const height = Math.round(width * aspect)
  if (!Number.isInteger(width) || width < 64 || width > 8192 || height < 1 || height > 8192 || width * height > 32 * 1024 * 1024)
    throw new Error('PNG宽度需64–8192像素，高度不超过8192，总像素不超过32MP。请调整分辨率。')
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  try {
    const image = new Image(); image.src = url; await image.decode()
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('当前浏览器无法创建PNG绘图上下文。')
    context.clearRect(0, 0, width, height); context.drawImage(image, 0, 0, width, height)
    return await new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG生成失败。')), 'image/png'))
  } finally { URL.revokeObjectURL(url) }
}
export function deliverDesign(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
