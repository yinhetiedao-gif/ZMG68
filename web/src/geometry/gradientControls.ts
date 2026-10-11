import type { BoundsMM } from '../model/types'
import type { Point } from './view'

/** Display-only interaction data, in the same world millimetres as Workspace2D. */
export type GradientControl =
  | { kind: 'linear' | 'region'; bounds: BoundsMM; values: { angle: number; scope_mode?: 'global' | 'local' | 'areas'; center_x?: number; center_y?: number; length?: number; width?: number } }
  | { kind: 'radial'; bounds: BoundsMM; values: { center_x: number; center_y: number; radius: number } }
export type GradientHandle = 'direction' | 'center' | 'radius' | 'start' | 'end' | 'width'
export function gradientMarkers(control: GradientControl) {
  if (control.kind === 'radial') return { center: { x: control.values.center_x, y: control.values.center_y },
    point: { x: control.values.center_x + control.values.radius, y: control.values.center_y } }
  const local = control.values.scope_mode === 'local'
  const center = local ? { x: control.values.center_x!, y: control.values.center_y! }
    : { x: (control.bounds.min_x + control.bounds.max_x) / 2, y: (control.bounds.min_y + control.bounds.max_y) / 2 }
  // This visual axis is NOT the field's start/end domain or an editable range.
  const length = local ? control.values.length! / 2 : Math.max(control.bounds.width, control.bounds.height) * .35
  const radians = control.values.angle * Math.PI / 180
  return { center, point: { x: center.x + Math.cos(radians) * length, y: center.y + Math.sin(radians) * length } }
}
export function gradientHandleChange(control: GradientControl, handle: GradientHandle, world: Point): Record<string, number> {
  const { center } = gradientMarkers(control)
  if (control.kind !== 'radial') {
    if (control.values.scope_mode === 'local') {
      if (handle === 'center') return { center_x: world.x, center_y: world.y }
      if (handle === 'width') {
        const r = control.values.angle * Math.PI / 180
        return { width: Math.max(.01, 2 * Math.abs(-(world.x-center.x)*Math.sin(r)+(world.y-center.y)*Math.cos(r))) }
      }
      const { point } = gradientMarkers(control)
      const other = handle === 'start' ? point : { x: 2*center.x-point.x, y: 2*center.y-point.y }
      const dx = handle === 'start' ? other.x-world.x : world.x-other.x
      const dy = handle === 'start' ? other.y-world.y : world.y-other.y
      if (Math.hypot(dx,dy) < .01) return {}
      return { center_x: (world.x+other.x)/2, center_y: (world.y+other.y)/2,
        length: Math.hypot(dx,dy), angle: Math.atan2(dy,dx)*180/Math.PI }
    }
    if (Math.hypot(world.x - center.x, world.y - center.y) < 1e-8) return {}
    return { angle: Math.atan2(world.y - center.y, world.x - center.x) * 180 / Math.PI }
  }
  return handle === 'center' ? { center_x: world.x, center_y: world.y }
    : { radius: Math.hypot(world.x - center.x, world.y - center.y) }
}
