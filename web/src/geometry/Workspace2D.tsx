import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import type { BoundsMM, FinalGeometry } from '../model/types'
import { geometryShape } from './render'
import { fitView, panBy, screenToWorld, zoomAt, type Point, type ViewTransform, type Viewport } from './view'
import type { ReferenceLayer } from '../document/referenceLayer'
import { gradientHandleChange, gradientMarkers, type GradientControl, type GradientHandle } from './gradientControls'
import { InfluenceControls, areaHandleChange } from './influenceControls'
import type { InfluenceArea } from '../document/designControls'

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
  onEditingChange?: (editing: boolean) => void
  referenceLayer?: (ReferenceLayer & { url: string }) | null
  onSelectReference?: () => void
  gradientControl?: GradientControl | null
  onGradientChange?: (values: Record<string, number>) => void
  artboard?: { x: number; y: number; width: number; height: number; grid: boolean }
  influenceAreas?: InfluenceArea[]
  selectedArea?: string
  onAreaChange?: (id: string, parameters: Record<string, number>) => void
}

type Interaction =
  | { kind: 'pan'; x: number; y: number; view: ViewTransform; nextX: number; nextY: number }
  | { kind: 'drag'; id: string; start: Point; node: SVGGElement; next: Point }
  | { kind: 'gradient'; control: GradientControl; handle: GradientHandle; start: Point }
  | { kind: 'area'; area: InfluenceArea; handle: string; start: Point }

export function Workspace2D({
  geometry, bounds, mmPerUnit, view, onViewChange, selectedId, onSelect,
  canDrag, onDragCommit, pendingPreview, fitToken, onEditingChange, referenceLayer, onSelectReference, gradientControl, onGradientChange,
  artboard, influenceAreas, selectedArea, onAreaChange,
}: Props) {
  const stage = useRef<HTMLDivElement>(null)
  const svg = useRef<SVGSVGElement>(null)
  const interaction = useRef<Interaction | null>(null)
  // Pointer frames temporarily own this DOM attribute. Reconcile it after
  // React commits, including a response that resolves before the next paint.
  const lastDragNode = useRef<SVGGElement | null>(null)
  const frame = useRef<number | null>(null)
  const lastCursorUpdate = useRef(0)
  const lastFitToken = useRef<number | null>(null)
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
    if (bounds && lastFitToken.current !== fitToken) {
      lastFitToken.current = fitToken
      onViewChange(fitView(bounds, viewport))
    }
    // A new Evaluate response after a drag must NOT re-fit the user's view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitToken, viewport.width, viewport.height])

  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    onEditingChange?.(false)
  }, [])

  useEffect(() => {
    if (interaction.current?.kind === 'gradient' && interaction.current.control.kind !== gradientControl?.kind) {
      interaction.current = null
      onEditingChange?.(false)
    }
  }, [gradientControl?.kind, onEditingChange])
  useEffect(() => {
    if (interaction.current?.kind === 'area' && !influenceAreas?.some(a => a.id === (interaction.current as Extract<Interaction, { kind: 'area' }>).area.id)) {
      interaction.current = null; onEditingChange?.(false)
    }
  }, [influenceAreas, onEditingChange])

  useLayoutEffect(() => {
    const node = lastDragNode.current
    if (!node || interaction.current?.kind === 'drag') return
    if (pendingPreview && pendingPreview.id === node.dataset.elementId) {
      node.setAttribute('transform', `translate(${pendingPreview.dx} ${pendingPreview.dy})`)
    } else {
      node.removeAttribute('transform')
      lastDragNode.current = null
    }
  }, [pendingPreview, geometry])

  const screenPoint = (event: { clientX: number; clientY: number }): Point => {
    const rect = svg.current?.getBoundingClientRect()
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) }
  }
  const fit = () => { if (bounds) onViewChange(fitView(bounds, viewport)) }
  const zoom = (factor: number) => onViewChange(zoomAt(view, factor, { x: viewport.width / 2, y: viewport.height / 2 }))
  const onWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    if (interaction.current?.kind === 'gradient' || interaction.current?.kind === 'area') return
    onViewChange(zoomAt(view, event.deltaY < 0 ? 1.12 : 1 / 1.12, screenPoint(event)))
  }
  const onGradientDown = (event: PointerEvent<SVGCircleElement>, handle: GradientHandle) => {
    if (event.button !== 0 || !gradientControl) return
    event.preventDefault(); event.stopPropagation()
    interaction.current = { kind: 'gradient', control: gradientControl, handle,
      start: screenToWorld(screenPoint(event), view) }
    onEditingChange?.(true)
    svg.current?.setPointerCapture?.(event.pointerId)
  }
  const changeGradient = (active: Extract<Interaction, { kind: 'gradient' }>, event: { clientX: number; clientY: number }) => {
    const world = screenToWorld(screenPoint(event), view)
    // Keep the grab offset when dragging the center, avoiding a pointerdown jump.
    const center = gradientMarkers(active.control).center
    const position = active.handle === 'center'
      ? { x: center.x + world.x - active.start.x, y: center.y + world.y - active.start.y } : world
    onGradientChange?.(gradientHandleChange(active.control, active.handle, position))
  }
  const onElementDown = (event: PointerEvent<SVGGElement>, item: FinalGeometry) => {
    if (event.button !== 0) return
    event.stopPropagation()
    onSelect(item.id)
    if (!canDrag(item)) return
    onEditingChange?.(true)
    interaction.current = {
      kind: 'drag', id: item.id, start: screenToWorld(screenPoint(event), view),
      node: event.currentTarget, next: { x: 0, y: 0 },
    }
    lastDragNode.current = event.currentTarget
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
    if (active.kind === 'gradient') { changeGradient(active, event); return }
    if (active.kind === 'area') {
      const world = screenToWorld(screen, view)
      onAreaChange?.(active.area.id, areaHandleChange(active.area, active.handle, world, { x: world.x - active.start.x, y: world.y - active.start.y })); return
    }
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
    onEditingChange?.(false)
    if (active.kind === 'gradient') { changeGradient(active, event); return }
    if (active.kind === 'area') {
      const world = screenToWorld(screenPoint(event), view)
      onAreaChange?.(active.area.id, areaHandleChange(active.area, active.handle, world, { x: world.x - active.start.x, y: world.y - active.start.y })); return
    }
    if (active.kind === 'pan') {
      onViewChange(panBy(active.view, event.clientX - active.x, event.clientY - active.y))
      return
    }
    const world = screenToWorld(screenPoint(event), view)
    const dx = world.x - active.start.x
    const dy = world.y - active.start.y
    if (Math.abs(dx) + Math.abs(dy) < 1e-8) {
      active.node.removeAttribute('transform')
      lastDragNode.current = null
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
    onEditingChange?.(false)
    if (active?.kind === 'gradient') onGradientChange?.(Object.fromEntries(Object.entries(active.control.values).filter(([, value]) => typeof value === 'number')) as Record<string, number>)
    if (active?.kind === 'area') onAreaChange?.(active.area.id, active.area.parameters)
    if (active?.kind === 'drag') {
      active.node.removeAttribute('transform')
      lastDragNode.current = null
    }
  }
  const markers = gradientControl ? gradientMarkers(gradientControl) : null
  const handleRadius = 7 / view.zoom

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
        onPointerUp={onUp} onPointerCancel={onCancel} onLostPointerCapture={onCancel}>
        <rect width={viewport.width} height={viewport.height} fill="transparent" />
        <g transform={`translate(${view.panX} ${view.panY}) scale(${view.zoom})`}>
          {artboard && <g pointerEvents="none" data-artboard="true">
            <defs><pattern id="design-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M 5 0 L 0 0 0 5" fill="none" stroke="#a4acb3" strokeWidth={.5 / view.zoom} /></pattern></defs>
            <rect x={artboard.x} y={artboard.y} width={artboard.width} height={artboard.height} fill={artboard.grid ? 'url(#design-grid)' : 'none'} stroke="#98a4ae" strokeDasharray="4 4" strokeWidth={1 / view.zoom} />
          </g>}
          {referenceLayer?.visible && referenceLayer.url && <image data-reference-layer="true"
            href={referenceLayer.url} x={referenceLayer.x_mm - referenceLayer.width_mm / 2}
            y={referenceLayer.y_mm - referenceLayer.height_mm / 2} width={referenceLayer.width_mm} height={referenceLayer.height_mm}
            opacity={referenceLayer.opacity} preserveAspectRatio="none"
            transform={`rotate(${referenceLayer.rotation_deg} ${referenceLayer.x_mm} ${referenceLayer.y_mm})`}
            pointerEvents={referenceLayer.locked ? 'none' : 'auto'}
            onPointerDown={event => { event.stopPropagation(); onSelectReference?.() }} />}
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
          {gradientControl && markers && <g data-gradient-controls={gradientControl.kind} className="gradient-controls">
            {gradientControl.kind === 'linear'
              ? <line data-gradient-axis="true" x1={2 * markers.center.x - markers.point.x} y1={2 * markers.center.y - markers.point.y}
                x2={markers.point.x} y2={markers.point.y} vectorEffect="non-scaling-stroke" pointerEvents="none" />
              : gradientControl.kind === 'radial' ? <circle data-gradient-range="true" cx={markers.center.x} cy={markers.center.y} r={gradientControl.values.radius}
                fill="none" vectorEffect="non-scaling-stroke" pointerEvents="none" /> : null}
            {gradientControl.kind !== 'radial' && gradientControl.values.scope_mode === 'local' && <>
              <rect data-gradient-range="true" x={markers.center.x-gradientControl.values.length!/2}
                y={markers.center.y-gradientControl.values.width!/2} width={gradientControl.values.length} height={gradientControl.values.width}
                transform={`rotate(${gradientControl.values.angle} ${markers.center.x} ${markers.center.y})`} fill="#00a2b510"
                vectorEffect="non-scaling-stroke" pointerEvents="none" />
              <circle data-gradient-handle="start" aria-label="拖动范围起点" cx={2*markers.center.x-markers.point.x} cy={2*markers.center.y-markers.point.y}
                r={handleRadius} vectorEffect="non-scaling-stroke" onPointerDown={event => onGradientDown(event, 'start')} />
              <circle data-gradient-handle="width" aria-label="拖动影响宽度"
                cx={markers.center.x-Math.sin(gradientControl.values.angle*Math.PI/180)*gradientControl.values.width!/2}
                cy={markers.center.y+Math.cos(gradientControl.values.angle*Math.PI/180)*gradientControl.values.width!/2}
                r={handleRadius} vectorEffect="non-scaling-stroke" onPointerDown={event => onGradientDown(event, 'width')} />
            </>}
            <circle data-gradient-handle={gradientControl.kind !== 'radial' ? gradientControl.values.scope_mode === 'local' ? 'end' : 'direction' : 'radius'}
              aria-label={gradientControl.kind !== 'radial' ? gradientControl.values.scope_mode === 'local' ? '拖动范围终点' : '拖动渐变方向' : '拖动影响半径'}
              cx={markers.point.x} cy={markers.point.y} r={handleRadius} vectorEffect="non-scaling-stroke"
              onPointerDown={event => onGradientDown(event, gradientControl.kind !== 'radial' ? gradientControl.values.scope_mode === 'local' ? 'end' : 'direction' : 'radius')} />
            {(gradientControl.kind === 'radial' || gradientControl.values.scope_mode === 'local') && <circle data-gradient-handle="center" aria-label="拖动渐变中心"
              cx={markers.center.x} cy={markers.center.y} r={handleRadius} vectorEffect="non-scaling-stroke"
              onPointerDown={event => onGradientDown(event, 'center')} />}
            <text x={markers.center.x} y={markers.center.y - 14 / view.zoom} fontSize={12 / view.zoom} pointerEvents="none">
              {gradientControl.kind !== 'radial' ? `${gradientControl.values.angle.toFixed(1)}° · ${gradientControl.values.scope_mode === 'local' ? '矩形内有效，外部保持原状态' : '全图方向'}`
                : `影响半径 ${gradientControl.values.radius.toFixed(2)} mm`}
            </text>
          </g>}
          {influenceAreas && <InfluenceControls areas={influenceAreas} selected={selectedArea} zoom={view.zoom} onDown={(event, area, handle) => {
            if (event.button !== 0) return
            event.preventDefault(); event.stopPropagation()
            const start = screenToWorld(screenPoint(event), view)
            interaction.current = { kind: 'area', area, handle, start }
            onEditingChange?.(true); onAreaChange?.(area.id, area.parameters)
            svg.current?.setPointerCapture?.(event.pointerId)
          }} />}
        </g>
      </svg>
      <div className="viewer-footer">
        <span>{geometry.length} 个元素 · mm</span>
        <span>{cursor ? `X ${cursor.x.toFixed(2)} mm · Y ${cursor.y.toFixed(2)} mm` : '左键空白处平移 · 滚轮缩放'}</span>
      </div>
    </div>
  )
}
