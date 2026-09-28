import { useEffect, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import type { BoundsMM, FinalGeometry } from '../model/types'
import { geometryShape } from './render'
import { fitView, panBy, screenToWorld, zoomAt, type Point, type ViewTransform, type Viewport } from './view'

interface Props {
  geometry: FinalGeometry[]
  bounds: BoundsMM | null
  mmPerUnit: number
  view: ViewTransform
  onViewChange: (view: ViewTransform) => void
  selectedId: string | null
  onSelect: (id: string | null) => void
  canDrag: (item: FinalGeometry) => boolean
  onDragCommit: (id: string, dxMm: number, dyMm: number) => void
  pendingPreview: { id: string; dx: number; dy: number } | null
  fitToken: number
}

type Interaction =
  | { kind: 'pan'; x: number; y: number; view: ViewTransform; nextX: number; nextY: number }
  | { kind: 'drag'; id: string; start: Point; node: SVGGElement; next: Point }

export function Workspace2D({
  geometry, bounds, mmPerUnit, view, onViewChange, selectedId, onSelect,
  canDrag, onDragCommit, pendingPreview, fitToken,
}: Props) {
  const stage = useRef<HTMLDivElement>(null)
  const svg = useRef<SVGSVGElement>(null)
  const interaction = useRef<Interaction | null>(null)
  const frame = useRef<number | null>(null)
  const lastCursorUpdate = useRef(0)
  const [viewport, setViewport] = useState<Viewport>({ width: 800, height: 600 })
  const [cursor, setCursor] = useState<Point | null>(null)

  useEffect(() => {
    const node = stage.current
    if (!node) return
    const update = () => {
      const rect = node.getBoundingClientRect()
      setViewport({ width: Math.max(rect.width, 1), height: Math.max(rect.height, 1) })
    }
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (bounds) onViewChange(fitView(bounds, viewport))
    // A new Evaluate response after a drag must NOT re-fit the user's view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitToken, viewport.width, viewport.height])

  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current)
  }, [])

  const screenPoint = (event: { clientX: number; clientY: number }): Point => {
    const rect = svg.current?.getBoundingClientRect()
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) }
  }
  const fit = () => { if (bounds) onViewChange(fitView(bounds, viewport)) }
  const zoom = (factor: number) => onViewChange(zoomAt(view, factor, { x: viewport.width / 2, y: viewport.height / 2 }))
  const onWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    onViewChange(zoomAt(view, event.deltaY < 0 ? 1.12 : 1 / 1.12, screenPoint(event)))
  }
  const onElementDown = (event: PointerEvent<SVGGElement>, item: FinalGeometry) => {
    if (event.button !== 0) return
    event.stopPropagation()
    onSelect(item.id)
    if (!canDrag(item)) return
    interaction.current = {
      kind: 'drag', id: item.id, start: screenToWorld(screenPoint(event), view),
      node: event.currentTarget, next: { x: 0, y: 0 },
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  const onBackgroundDown = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 && event.button !== 1) return
    onSelect(null)
    interaction.current = {
      kind: 'pan', x: event.clientX, y: event.clientY, view,
      nextX: event.clientX, nextY: event.clientY,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const screen = screenPoint(event)
    const now = performance.now()
    if (now - lastCursorUpdate.current >= 75) {
      lastCursorUpdate.current = now
      setCursor(screenToWorld(screen, view))
    }
    const active = interaction.current
    if (!active) return
    if (active.kind === 'drag') {
      const world = screenToWorld(screen, view)
      active.next = { x: world.x - active.start.x, y: world.y - active.start.y }
    } else {
      active.nextX = event.clientX
      active.nextY = event.clientY
    }
    if (frame.current !== null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      const current = interaction.current
      if (current?.kind === 'drag') {
        current.node.setAttribute('transform', `translate(${current.next.x} ${current.next.y})`)
      } else if (current?.kind === 'pan') {
        onViewChange(panBy(current.view, current.nextX - current.x, current.nextY - current.y))
      }
    })
  }
  const onUp = (event: PointerEvent<SVGSVGElement>) => {
    const active = interaction.current
    if (!active) return
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
      frame.current = null
    }
    interaction.current = null
    if (active.kind === 'pan') {
      onViewChange(panBy(active.view, event.clientX - active.x, event.clientY - active.y))
      return
    }
    const world = screenToWorld(screenPoint(event), view)
    const dx = world.x - active.start.x
    const dy = world.y - active.start.y
    if (Math.abs(dx) + Math.abs(dy) < 1e-8) {
      active.node.removeAttribute('transform')
      return
    }
    active.node.setAttribute('transform', `translate(${dx} ${dy})`)
    onDragCommit(active.id, dx, dy)
  }
  const onCancel = () => {
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
      frame.current = null
    }
    const active = interaction.current
    interaction.current = null
    if (active?.kind === 'drag') active.node.removeAttribute('transform')
  }

  return (
    <div className="viewer-root" ref={stage} aria-label="二维设计画布">
      <div className="viewer-controls">
        <button type="button" onClick={fit} disabled={!bounds}>适合窗口</button>
        <button type="button" aria-label="缩小" onClick={() => zoom(1 / 1.2)}>−</button>
        <span aria-label="当前缩放">{view.zoom.toFixed(2)} px/mm</span>
        <button type="button" aria-label="放大" onClick={() => zoom(1.2)}>＋</button>
        <button type="button" onClick={fit} disabled={!bounds}>重置视角</button>
      </div>
      <svg ref={svg} className="viewer-svg" role="img" aria-label="最终二维几何，单位毫米"
        viewBox={`0 0 ${viewport.width} ${viewport.height}`}
        onWheel={onWheel} onPointerDown={onBackgroundDown} onPointerMove={onMove}
        onPointerUp={onUp} onPointerCancel={onCancel}>
        <rect width={viewport.width} height={viewport.height} fill="transparent" />
        <g transform={`translate(${view.panX} ${view.panY}) scale(${view.zoom})`}>
          {geometry.map((item) => (
            <g key={item.id} data-element-id={item.id}
              transform={pendingPreview?.id === item.id ? `translate(${pendingPreview.dx} ${pendingPreview.dy})` : undefined}
              className={selectedId === item.id ? 'geometry-item selected' : 'geometry-item'}
              onPointerDown={(event) => onElementDown(event, item)}>
              {geometryShape(item, mmPerUnit)}
              {selectedId === item.id && <rect className="selection-bounds" pointerEvents="none"
                x={item.x - item.width / 2} y={item.y - item.height / 2}
                width={item.width} height={item.height}
                transform={item.rotation ? `rotate(${item.rotation} ${item.x} ${item.y})` : undefined} />}
            </g>
          ))}
        </g>
      </svg>
      <div className="viewer-footer">
        <span>{geometry.length} 个元素 · mm</span>
        <span>{cursor ? `X ${cursor.x.toFixed(2)} mm · Y ${cursor.y.toFixed(2)} mm` : '左键空白处平移 · 滚轮缩放'}</span>
      </div>
    </div>
  )
}
