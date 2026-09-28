import { describe, expect, it } from 'vitest'
import { fitView, panBy, screenToWorld, worldToScreen, zoomAt } from './view'

describe('single mm ↔ px coordinate transform', () => {
  const bounds = { min_x: 10, min_y: 20, max_x: 110, max_y: 70, width: 100, height: 50, units: 'mm' as const }

  it('fits mm bounds into a pixel viewport', () => {
    const view = fitView(bounds, { width: 800, height: 600 })
    expect(view.zoom).toBeCloseTo(7.04)
    expect(worldToScreen({ x: 60, y: 45 }, view)).toEqual({ x: 400, y: 300 })
  })

  it('round-trips at 50%, 100%, 200% and after pan', () => {
    for (const zoom of [0.5, 1, 2]) {
      const view = panBy({ zoom, panX: 16, panY: -33 }, 210, 74)
      const world = { x: 42.25, y: -5.5 }
      const restored = screenToWorld(worldToScreen(world, view), view)
      expect(restored.x).toBeCloseTo(world.x)
      expect(restored.y).toBeCloseTo(world.y)
    }
  })

  it('keeps the world point below the cursor fixed while zooming', () => {
    const old = fitView(bounds, { width: 800, height: 600 })
    const cursor = { x: 230, y: 190 }
    const zoomed = zoomAt(old, 1.5, cursor)
    expect(screenToWorld(cursor, zoomed).x).toBeCloseTo(screenToWorld(cursor, old).x)
    expect(screenToWorld(cursor, zoomed).y).toBeCloseTo(screenToWorld(cursor, old).y)
  })
})
