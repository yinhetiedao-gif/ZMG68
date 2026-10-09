import type { BoundsMM } from '../model/types'
import type { Point } from './view'

/** Display-only interaction data, in the same world millimetres as Workspace2D. */
export type GradientControl =
  | { kind: 'linear'; bounds: BoundsMM; values: { angle: number } }
  | { kind: 'radial'; bounds: BoundsMM; values: { center_x: number; center_y: number; radius: number } }
export type GradientHandle = 'direction' | 'center' | 'radius'
export function gradientMarkers(control: GradientControl) {
  if (control.kind === 'radial') return { center: { x: control.values.center_x, y: control.values.center_y },
    point: { x: control.values.center_x + control.values.radius, y: control.values.center_y } }
  const center = { x: (control.bounds.min_x + control.bounds.max_x) / 2, y: (control.bounds.min_y + control.bounds.max_y) / 2 }
  // This visual axis is NOT the field's start/end domain or an editable range.
  const length = Math.max(control.bounds.width, control.bounds.height) * .35
  const radians = control.values.angle * Math.PI / 180
  return { center, point: { x: center.x + Math.cos(radians) * length, y: center.y + Math.sin(radians) * length } }
}
export function gradientHandleChange(control: GradientControl, handle: GradientHandle, world: Point): Record<string, number> {
  const { center } = gradientMarkers(control)
  if (control.kind === 'linear') {
    if (Math.hypot(world.x - center.x, world.y - center.y) < 1e-8) return {}
    return { angle: Math.atan2(world.y - center.y, world.x - center.x) * 180 / Math.PI }
  }
  return handle === 'center' ? { center_x: world.x, center_y: world.y }
    : { radius: Math.hypot(world.x - center.x, world.y - center.y) }
}
