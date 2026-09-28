import type { BoundsMM } from '../model/types'

export interface Point { x: number; y: number }
export interface Viewport { width: number; height: number }
export interface ViewTransform { zoom: number; panX: number; panY: number }

export const initialView: ViewTransform = { zoom: 1, panX: 0, panY: 0 }

/** The only World(mm) <-> view/screen(px) mapping used by render and pointer interaction. */
export function worldToScreen(point: Point, view: ViewTransform): Point {
  return { x: point.x * view.zoom + view.panX, y: point.y * view.zoom + view.panY }
}

export function screenToWorld(point: Point, view: ViewTransform): Point {
  return { x: (point.x - view.panX) / view.zoom, y: (point.y - view.panY) / view.zoom }
}

export function fitView(bounds: BoundsMM, viewport: Viewport, padding = 48): ViewTransform {
  const usableX = Math.max(1, viewport.width - 2 * padding)
  const usableY = Math.max(1, viewport.height - 2 * padding)
  const zoom = Math.min(usableX / Math.max(bounds.width, 1), usableY / Math.max(bounds.height, 1))
  const centerX = (bounds.min_x + bounds.max_x) / 2
  const centerY = (bounds.min_y + bounds.max_y) / 2
  return { zoom, panX: viewport.width / 2 - centerX * zoom, panY: viewport.height / 2 - centerY * zoom }
}

export function zoomAt(view: ViewTransform, factor: number, screen: Point): ViewTransform {
  const before = screenToWorld(screen, view)
  const zoom = Math.max(0.02, Math.min(200, view.zoom * factor))
  return { zoom, panX: screen.x - before.x * zoom, panY: screen.y - before.y * zoom }
}

export function panBy(view: ViewTransform, dx: number, dy: number): ViewTransform {
  return { ...view, panX: view.panX + dx, panY: view.panY + dy }
}
