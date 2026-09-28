import type { ReactNode } from 'react'
import type { FinalGeometry } from '../model/types'

function styleValue(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback
  // Keep literal colour names/hex/rgb, but refuse external URL references.
  return /url\s*\(/i.test(value) ? fallback : value
}

function pathTransform(item: FinalGeometry, mmPerUnit: number): string {
  const source = item.source_transform?.trim() ?? ''
  const x = item.x / mmPerUnit
  const y = item.y / mmPerUnit
  const baseX = (item.base_x ?? 0) / mmPerUnit
  const baseY = (item.base_y ?? 0) / mmPerUnit
  const baseWidth = (item.base_width ?? mmPerUnit) / mmPerUnit
  const baseHeight = (item.base_height ?? mmPerUnit) / mmPerUnit
  const parts = source ? [source] : []
  if (x !== baseX || y !== baseY) parts.push(`translate(${x - baseX} ${y - baseY})`)
  if (item.width / mmPerUnit !== baseWidth || item.height / mmPerUnit !== baseHeight) {
    parts.push(`translate(${baseX} ${baseY})`)
    parts.push(`scale(${item.width / mmPerUnit / Math.max(baseWidth, 1e-9)} ${item.height / mmPerUnit / Math.max(baseHeight, 1e-9)})`)
    parts.push(`translate(${-baseX} ${-baseY})`)
  }
  if (item.rotation) parts.push(`rotate(${item.rotation} ${baseX} ${baseY})`)
  return parts.join(' ')
}

/** SVG primitives represent exactly the five geometry types emitted by WM2/WM3 today. */
export function geometryShape(item: FinalGeometry, mmPerUnit: number): ReactNode {
  const style = item.style ?? {}
  const filled = item.type === 'filled_region'
  const fill = styleValue(style.fill, '#000000')
  const stroke = filled ? 'none' : styleValue(style.stroke, 'none')
  const strokeWidth = typeof style['stroke-width'] === 'number' || typeof style['stroke-width'] === 'string'
    ? Number(style['stroke-width']) : undefined
  const opacity = typeof style.opacity === 'number' ? style.opacity : undefined
  const common = { fill, stroke, strokeWidth: Number.isFinite(strokeWidth) ? strokeWidth : undefined, opacity }
  const rotation = item.rotation ? `rotate(${item.rotation} ${item.x} ${item.y})` : undefined
  switch (item.type) {
    case 'circle':
      return <circle cx={item.x} cy={item.y} r={item.width / 2} transform={rotation} {...common} />
    case 'ellipse':
      return <ellipse cx={item.x} cy={item.y} rx={item.width / 2} ry={item.height / 2} transform={rotation} {...common} />
    case 'rect':
      return <rect x={item.x - item.width / 2} y={item.y - item.height / 2}
        width={item.width} height={item.height} rx={item.rx} ry={item.ry} transform={rotation} {...common} />
    case 'path':
    case 'filled_region':
      return <g transform={`scale(${mmPerUnit})`}>
        <path d={item.path_data} transform={pathTransform(item, mmPerUnit)}
          fillRule={style['fill-rule'] === 'evenodd' ? 'evenodd' : 'nonzero'} {...common} />
      </g>
  }
}
