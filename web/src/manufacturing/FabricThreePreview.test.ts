import { describe, expect, it } from 'vitest'
import { Object3D, Vector3 } from 'three'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { FabricThreePreview, fabricHeightColor, fabricPreviewPalette, setFabricInstanceTransform } from './FabricThreePreview'
import type { FabricDesignPreview, FabricPreviewInstance } from '../api/fabricPreview'

const instance: FabricPreviewInstance = {
  id: 'fabric:final:square-1', source_id: 'square-1', final_geometry_id: 'square-1',
  x_mm: 24, y_mm: 31, z_mm: .6, rotation_deg: 90,
  scale: 1, scale_x: 1.5, scale_y: .75, enabled: true,
  cell_type: 'fin', base_width_mm: 4, base_depth_mm: 2, base_height_mm: 3,
  cell_width_mm: 6, cell_depth_mm: 1.5, cell_height_mm: 3, height_mm: 3,
}

describe('Fabric instance transform', () => {
  it('groups styles and framing in one toolbar, keeps warnings and does not add manufacture actions', () => {
    const plan = { active_count: 9, count: 9, total_count: 100, preview_simplified: true,
      skipped_count: 2, unmatched_reference_count: 1 } as FabricDesignPreview
    const html = renderToStaticMarkup(createElement(FabricThreePreview, {plan, stale: true}))
    const dom = new DOMParser().parseFromString(html, 'text/html')
    const toolbar = dom.querySelector('.fabric-preview-toolbar')!
    expect(toolbar.querySelector('[aria-label="预览样式"]')).not.toBeNull()
    expect([...toolbar.querySelectorAll('button')].map(button => button.textContent)).toEqual(['适合窗口', '重置视角'])
    expect(dom.querySelectorAll('option')).toHaveLength(3)
    expect(dom.querySelector('.fabric-preview-summary [role=status]')?.textContent).toContain('上次预览，已失效')
    expect(html).toContain('显示 9 / 100'); expect(html).toContain('跳过 2'); expect(html).toContain('1 个元素缺少稳定基准尺寸')
    expect(html).not.toContain('下载'); expect(html).not.toContain('最终制造已通过')
  })
  it('labels retained stale geometry as an old preview, not ready', () => {
    const plan = { active_count: 4160 } as FabricDesignPreview
    const html = renderToStaticMarkup(createElement(FabricThreePreview, {plan, stale: true}))
    expect(html).toContain('上次预览，已失效 · 4160 个可见实例')
    expect(html).not.toContain('已就绪')
    expect(plan).toEqual({active_count: 4160})
  })
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
    setFabricInstanceTransform(dummy, { ...instance, scale: 1.2, scale_x: 1.5, scale_y: .75,
      cell_width_mm: 7.2, cell_depth_mm: 1.8, cell_height_mm: 6, height_mm: 6 })
    expect(dummy.scale.x).toBeCloseTo(1.8)
    expect(dummy.scale.y).toBeCloseTo(.9)
    expect(dummy.scale.z).toBeCloseTo(2)
    expect(dummy.position.z).toBe(.6)
    expect(dummy.rotation.z).toBeCloseTo(Math.PI / 2)
  })
  it('uses explicit final dimensions once in fixed and follow-pattern modes', () => {
    const dummy = new Object3D()
    setFabricInstanceTransform(dummy, { ...instance, scale_x: 2, scale_y: 3,
      cell_width_mm: 4, cell_depth_mm: 2 })
    expect(dummy.scale.toArray()).toEqual([1, 1, 1])
    setFabricInstanceTransform(dummy, { ...instance, scale_x: 2, scale_y: 3,
      cell_width_mm: 8, cell_depth_mm: 6 })
    expect(dummy.scale.toArray()).toEqual([2, 3, 1])
  })
  it('maps height to preview color without changing the instance transform', () => {
    expect(fabricHeightColor(1, 1, 10).getHex()).not.toBe(fabricHeightColor(10, 1, 10).getHex())
    expect(fabricHeightColor(5, 5, 5).getHex()).toBe(fabricHeightColor(7, 7, 7).getHex())
  })
  it('keeps preview styles visual-only with white background and black high-contrast cells', () => {
    expect(fabricPreviewPalette('high_contrast')).toMatchObject({ background: 0xffffff, cell: 0x000000 })
    expect(fabricPreviewPalette('height_map')).toMatchObject({ background: 0xffffff, cell: 0xffffff })
    expect(fabricPreviewPalette('default').cell).not.toBe(0x000000)
  })
})
