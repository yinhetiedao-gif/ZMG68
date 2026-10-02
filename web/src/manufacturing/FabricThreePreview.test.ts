import { describe, expect, it } from 'vitest'
import { Object3D, Vector3 } from 'three'
import { setFabricInstanceTransform } from './FabricThreePreview'
import type { FabricPreviewInstance } from '../api/fabricPreview'

const instance: FabricPreviewInstance = {
  id: 'fabric:final:square-1', source_id: 'square-1', final_geometry_id: 'square-1',
  x_mm: 24, y_mm: 31, z_mm: .6, rotation_deg: 90,
  scale: 1, scale_x: 1.5, scale_y: .75, enabled: true,
  cell_type: 'fin', base_width_mm: 4, base_depth_mm: 2, base_height_mm: 3, height_mm: 3,
}

describe('Fabric instance transform', () => {
  it('applies final translation, XY scale and Z rotation exactly once', () => {
    const dummy = new Object3D()
    setFabricInstanceTransform(dummy, instance)
    expect(dummy.position.toArray()).toEqual([24, 31, .6])
    expect(dummy.scale.toArray()).toEqual([1.5, .75, 1])
    expect(dummy.rotation.z).toBeCloseTo(Math.PI / 2)
    const localX = new Vector3(2, 0, 0).applyMatrix4(dummy.matrix)
    expect(localX.x).toBeCloseTo(24)
    expect(localX.y).toBeCloseTo(34)
    expect(localX.z).toBeCloseTo(.6)
  })
  it('composes Fabric scale with Pattern XY once and maps independent height to Z', () => {
    const dummy = new Object3D()
    setFabricInstanceTransform(dummy, { ...instance, scale: 1.2, height_mm: 6 })
    expect(dummy.scale.x).toBeCloseTo(1.8)
    expect(dummy.scale.y).toBeCloseTo(.9)
    expect(dummy.scale.z).toBeCloseTo(2)
    expect(dummy.position.z).toBe(.6)
    expect(dummy.rotation.z).toBeCloseTo(Math.PI / 2)
  })
})
