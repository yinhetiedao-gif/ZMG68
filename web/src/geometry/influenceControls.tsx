import type { InfluenceArea } from '../document/designControls'
import type { PointerEvent } from 'react'
import type { Point } from './view'

export function areaHandles(area: InfluenceArea) {
  const p = area.parameters
  if (area.type === 'curve') {
    const center = { x: (p.x0 + 2 * p.x1 + p.x2) / 4, y: (p.y0 + 2 * p.y1 + p.y2) / 4 }
    const theta = Math.atan2(p.y2 - p.y0, p.x2 - p.x0)
    return { center, start: { x: p.x0, y: p.y0 }, control: { x: p.x1, y: p.y1 }, end: { x: p.x2, y: p.y2 },
      width: { x: center.x - Math.sin(theta) * p.width / 2, y: center.y + Math.cos(theta) * p.width / 2 } }
  }
  const theta = p.angle * Math.PI / 180, dx = Math.cos(theta) * p.length / 2, dy = Math.sin(theta) * p.length / 2
  return { center: { x: p.x, y: p.y }, start: { x: p.x - dx, y: p.y - dy }, end: { x: p.x + dx, y: p.y + dy },
    width: { x: p.x - Math.sin(theta) * p.width / 2, y: p.y + Math.cos(theta) * p.width / 2 } }
}
export function areaHandleChange(area: InfluenceArea, handle: string, world: Point, delta: Point) {
  const p = area.parameters, marks = areaHandles(area)
  if (handle === 'center') return area.type === 'curve' ? Object.fromEntries([0, 1, 2].flatMap(i => [[`x${i}`, p[`x${i}`] + delta.x], [`y${i}`, p[`y${i}`] + delta.y]]))
    : { x: p.x + delta.x, y: p.y + delta.y }
  if (handle === 'width') {
    const theta = area.type === 'curve' ? Math.atan2(p.y2 - p.y0, p.x2 - p.x0) : p.angle * Math.PI / 180
    const width = Math.max(.02, 2 * Math.abs(-(world.x - marks.center.x) * Math.sin(theta) + (world.y - marks.center.y) * Math.cos(theta)))
    return { width, feather: Math.min(p.feather, width / 2) }
  }
  if (area.type === 'curve') {
    const i = handle === 'start' ? 0 : handle === 'control' ? 1 : 2
    return { [`x${i}`]: world.x, [`y${i}`]: world.y }
  }
  if (area.type === 'ellipse') {
    return { length: Math.max(.02, 2 * Math.hypot(world.x - p.x, world.y - p.y)), angle: Math.atan2(world.y - p.y, world.x - p.x) * 180 / Math.PI }
  }
  const fixed = handle === 'start' ? marks.end : marks.start
  const start = handle === 'start' ? world : fixed, end = handle === 'start' ? fixed : world
  return { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2,
    length: Math.max(.02, Math.hypot(end.x - start.x, end.y - start.y)), angle: Math.atan2(end.y - start.y, end.x - start.x) * 180 / Math.PI }
}
export function InfluenceControls({ areas, selected, zoom, onDown }: { areas: InfluenceArea[]; selected?: string; zoom: number;
  onDown: (event: PointerEvent<SVGCircleElement>, area: InfluenceArea, handle: string) => void }) {
  return <g className="gradient-controls" data-influence-controls="true">{areas.map(a => {
    const p = a.parameters, h = areaHandles(a), active = a.id === (selected ?? areas[0]?.id)
    return <g key={a.id} opacity={a.enabled ? active ? 1 : .3 : .16} data-influence-id={a.id}>
      {a.type === 'ellipse' ? <ellipse cx={p.x} cy={p.y} rx={p.length / 2} ry={p.width / 2} transform={`rotate(${p.angle} ${p.x} ${p.y})`}
        fill="var(--influence-fill)" vectorEffect="non-scaling-stroke" pointerEvents="none" />
        : <path d={a.type === 'curve' ? `M ${p.x0} ${p.y0} Q ${p.x1} ${p.y1} ${p.x2} ${p.y2}` : `M ${h.start.x} ${h.start.y} L ${h.end.x} ${h.end.y}`}
          fill="none" stroke="var(--brand)" strokeWidth={p.width} strokeLinecap="round" style={{ stroke: 'var(--influence-stroke)', strokeWidth: p.width }} pointerEvents="none" />}
      {a.type === 'curve' && <path d={`M ${p.x0} ${p.y0} L ${p.x1} ${p.y1} L ${p.x2} ${p.y2}`} fill="none" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
      {Object.entries(h).map(([key, point]) => <circle key={key} aria-label={`拖动${a.id} ${key}`} data-area-handle={key} data-area-id={a.id}
        cx={point.x} cy={point.y} r={7 / zoom} vectorEffect="non-scaling-stroke" onPointerDown={e => onDown(e, a, key)} />)}
      <text x={h.center.x} y={h.center.y - 14 / zoom} fontSize={12 / zoom} pointerEvents="none">{a.id} · {a.type}</text>
    </g>
  })}</g>
}
