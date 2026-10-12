import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AmbientLight, Box3, BoxGeometry, BufferGeometry, Color, DirectionalLight,
  DoubleSide, Float32BufferAttribute, Group, InstancedMesh, MeshPhongMaterial,
  Object3D, PerspectiveCamera, Scene, Vector3, WebGLRenderer } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { FabricDesignPreview, FabricPreviewInstance } from '../api/fabricPreview'

export type FabricPreviewStyle = 'default' | 'high_contrast' | 'height_map'

export function fabricPreviewPalette(style: FabricPreviewStyle) {
  return style === 'high_contrast'
    ? { background: 0xffffff, cell: 0x000000, base: 0xc8cdd1 }
    : style === 'height_map'
      ? { background: 0xffffff, cell: 0xffffff, base: 0xc8cdd1 }
      : { background: 0xf9fbfc, cell: 0x668ca1, base: 0x4b5961 }
}

export function fabricHeightColor(height: number, minHeight: number, maxHeight: number): Color {
  const ratio = maxHeight > minHeight ? Math.min(1, Math.max(0, (height - minHeight) / (maxHeight - minHeight))) : .5
  return new Color().setHSL((1 - ratio) * .66, .9, .48)
}

export function setFabricInstanceTransform(dummy: Object3D, instance: FabricPreviewInstance) {
  dummy.position.set(instance.x_mm, instance.y_mm, instance.z_mm)
  dummy.rotation.set(0, 0, instance.rotation_deg * Math.PI / 180)
  dummy.scale.set(instance.cell_width_mm / instance.base_width_mm!,
    instance.cell_depth_mm / instance.base_depth_mm!,
    instance.cell_height_mm / instance.base_height_mm!)
  dummy.updateMatrix()
}

export function FabricThreePreview({ plan, stale = false, diagnosticsHost }: {
  plan: FabricDesignPreview; stale?: boolean; diagnosticsHost?: HTMLElement | null
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fitRef = useRef<(() => void) | null>(null)
  const resetRef = useRef<(() => void) | null>(null)
  const [status, setStatus] = useState('正在准备 Fabric 设计预览…')
  const [bounds, setBounds] = useState<string | null>(null)
  const [updateMs, setUpdateMs] = useState<string | null>(null)
  const [style, setStyle] = useState<FabricPreviewStyle>('default')
  const latest = useRef({ plan, style }); latest.current = { plan, style }
  const updateRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    if (!host || !canvas) return
    let disposed = false
    let frame = 0
    let renderer: WebGLRenderer | null = null
    let controls: OrbitControls | null = null
    let observer: ResizeObserver | null = null
    const palette = fabricPreviewPalette(style)
    const material = new MeshPhongMaterial({ color: palette.cell, side: DoubleSide })
    const baseMaterial = new MeshPhongMaterial({ color: palette.base, side: DoubleSide })
    const group = new Group()
    const scene = new Scene()
    scene.background = new Color(palette.background)
    const camera = new PerspectiveCamera(45, 1, 0.01, 100000)
    camera.up.set(0, 0, 1)
    scene.add(new AmbientLight(0xffffff, 2.2))
    const light = new DirectionalLight(0xffffff, 2.8)
    light.position.set(1, -2, 3)
    scene.add(light)
    try {
      renderer = new WebGLRenderer({ canvas, antialias: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      controls = new OrbitControls(camera, canvas)
      controls.enableDamping = true
      canvas.dataset.rendererInitializations = String(Number(canvas.dataset.rendererInitializations ?? 0) + 1)
      let initialized = false
      let geometryKey = ''
      let cells: { mesh: InstancedMesh; key: string }[] = []
      const update = () => {
        const started = performance.now()
        const { plan, style } = latest.current
        const palette = fabricPreviewPalette(style)
        scene.background = new Color(palette.background)
        material.color.setHex(palette.cell); baseMaterial.color.setHex(palette.base)
        const active = plan.instances.filter(instance => instance.enabled)
        const meshGroups = new Map<string, { prototype: NonNullable<FabricDesignPreview['prototype']>; instances: FabricPreviewInstance[] }>()
        for (const instance of active) {
          const prototype = plan.contour_prototypes ? plan.contour_prototypes[instance.id] : plan.prototype
          if (!prototype) continue
          const key = plan.contour_prototypes ? JSON.stringify(prototype) : 'shared'
          const group = meshGroups.get(key) ?? { prototype, instances: [] }
          group.instances.push(instance); meshGroups.set(key, group)
        }
        const nextGeometryKey = JSON.stringify([plan.output_mode, plan.base_preview, plan.prototype,
          [...meshGroups].map(([key, value]) => [key, value.instances.length])])
        if (nextGeometryKey !== geometryKey) {
          for (const node of [...group.children]) {
            if (node instanceof InstancedMesh) { node.geometry.dispose(); node.dispose() }
            group.remove(node)
          }
          cells = []
          geometryKey = nextGeometryKey
          const [left, bottom, right, top] = plan.base_preview.bounds_mm
          const thickness = plan.base_preview.thickness_mm
          const boxes: [number, number, number, number, number, number][] = []
          if (plan.output_mode === 'cells_only') {
            // Bounds still support placement; they are not a physical base.
          } else if (plan.base_preview.type === 'solid') {
            boxes.push([(left + right) / 2, (bottom + top) / 2, thickness / 2,
              right - left, top - bottom, thickness])
          } else {
            const sx = plan.base_preview.spacing_x_mm ?? 1
            const sy = plan.base_preview.spacing_y_mm ?? 1
            const width = plan.base_preview.line_width_mm ?? 1
            const columns = Math.ceil((right - left) / sx)
            const rows = Math.ceil((top - bottom) / sy)
            for (let index = 0; index <= columns; index++) {
              const x = index === columns ? right : left + index * sx
              const start = Math.max(left, x - width / 2)
              const end = Math.min(right, x + width / 2)
              boxes.push([(start + end) / 2, (bottom + top) / 2, thickness / 2,
                end - start, top - bottom, thickness])
            }
            for (let index = 0; index <= rows; index++) {
              const y = index === rows ? top : bottom + index * sy
              const start = Math.max(bottom, y - width / 2)
              const end = Math.min(top, y + width / 2)
              boxes.push([(left + right) / 2, (start + end) / 2, thickness / 2,
                right - left, end - start, thickness])
            }
          }
          const dummy = new Object3D()
          const baseMesh = new InstancedMesh(new BoxGeometry(1, 1, 1), baseMaterial, boxes.length)
          boxes.forEach(([x, y, z, w, h, d], index) => {
            dummy.position.set(x, y, z)
            dummy.scale.set(w, h, d)
            dummy.rotation.set(0, 0, 0)
            dummy.updateMatrix()
            baseMesh.setMatrixAt(index, dummy.matrix)
          })
          baseMesh.instanceMatrix.needsUpdate = true
          if (boxes.length) { baseMesh.computeBoundingSphere(); group.add(baseMesh) }
          else baseMesh.geometry.dispose()
          for (const [key, bundle] of meshGroups) {
            const geometry = new BufferGeometry()
            geometry.setAttribute('position', new Float32BufferAttribute(bundle.prototype.vertices.flat(), 3))
            geometry.setIndex(bundle.prototype.faces.flat())
            geometry.computeVertexNormals()
            const instances = new InstancedMesh(geometry, material, bundle.instances.length)
            cells.push({ mesh: instances, key })
            group.add(instances)
          }
        }
        const heights = active.map((instance) => instance.height_mm)
        const minHeight = Math.min(...heights)
        const maxHeight = Math.max(...heights)
        for (const bundle of cells) {
          const instances = bundle.mesh
          const selected = meshGroups.get(bundle.key)!.instances
          const dummy = new Object3D()
          if (style !== 'height_map') instances.instanceColor = null
          selected.forEach((instance, index) => {
            setFabricInstanceTransform(dummy, instance)
            instances.setMatrixAt(index, dummy.matrix)
            if (style === 'height_map') instances.setColorAt(index,
              fabricHeightColor(instance.height_mm, minHeight, maxHeight))
          })
          instances.instanceMatrix.needsUpdate = true
          if (instances.instanceColor) instances.instanceColor.needsUpdate = true
          // Color belongs to the instance buffer, not an extra vertex-color attribute.
          material.needsUpdate = true
          instances.computeBoundingBox()
          instances.computeBoundingSphere()
        }
        const box = new Box3().setFromObject(group)
        const center = box.getCenter(new Vector3())
        const size = box.getSize(new Vector3())
        setBounds(`${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} mm`)
        const fit = (reset: boolean) => {
          const maxSize = Math.max(size.x, size.y, size.z, 1)
          const distance = maxSize / (2 * Math.tan(camera.fov * Math.PI / 360)) * 1.8
          const direction = reset ? new Vector3(1, -1, .8).normalize()
            : camera.position.clone().sub(controls!.target).normalize()
          camera.near = Math.max(.001, distance / 1000)
          camera.far = distance * 1000
          camera.position.copy(center).addScaledVector(direction, distance)
          camera.updateProjectionMatrix()
          controls!.target.copy(center)
          controls!.update()
        }
        fitRef.current = () => fit(false)
        resetRef.current = () => fit(true)
        if (!initialized && active.length) { fit(true); initialized = true }
        setStatus(`Fabric 设计预览已就绪 · ${plan.active_count} 个${plan.shape_source === 'original' ? '原图元素' : '可见共享原型实例'}`)
        setUpdateMs((performance.now() - started).toFixed(1))
      }
      updateRef.current = update
      scene.add(group)
      update()
      const resize = () => {
        if (!renderer) return
        camera.aspect = Math.max(1, host.clientWidth) / Math.max(1, host.clientHeight)
        camera.updateProjectionMatrix()
        renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false)
      }
      resize()
      observer = new ResizeObserver(resize)
      observer.observe(host)
      const animate = () => {
        if (disposed || !renderer || !controls) return
        frame = requestAnimationFrame(animate)
        controls.update()
        renderer.render(scene, camera)
      }
      animate()
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Fabric 设计预览失败。')
    }
    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      observer?.disconnect()
      controls?.dispose()
      group.traverse((node) => { if (node instanceof InstancedMesh) node.geometry.dispose() })
      material.dispose()
      baseMaterial.dispose()
      renderer?.dispose()
      fitRef.current = null
      resetRef.current = null
      updateRef.current = null
    }
  }, [])
  useLayoutEffect(() => { updateRef.current?.() }, [plan, style])

  return <div className="three-preview" aria-label="Fabric 设计预览">
    <div className="three-preview-toolbar fabric-preview-toolbar">
      <label htmlFor="fabric-preview-style">样式</label>
      <select id="fabric-preview-style" aria-label="预览样式" value={style} onChange={(event) => setStyle(event.target.value as FabricPreviewStyle)}>
        <option value="default">默认实体</option>
        <option value="high_contrast">高对比 · 白底黑色单元</option>
        <option value="height_map">高度图 · 颜色仅用于预览</option>
      </select>
      <button type="button" onClick={() => fitRef.current?.()} disabled={!bounds}>适合窗口</button>
      <button type="button" onClick={() => resetRef.current?.()} disabled={!bounds}>重置视角</button></div>
    <div className="three-preview-viewport" ref={hostRef}><canvas ref={canvasRef} aria-label="Fabric 设计三维画布" /></div>
    <div className="fabric-preview-summary">
      <span className="three-preview-status" role="status">{stale ? `上次预览，已失效 · ${plan.active_count} 个可见实例` : status}</span>
      {bounds && <small className="three-preview-bounds">预览 XYZ：{bounds}</small>}
    </div>
    {diagnosticsHost && createPortal(<p>Fabric 设计预览 · 浏览器实例更新：{updateMs === null ? '尚未完成' : `${updateMs} ms`}
      {stale ? ' · 上次结果，已失效' : ''}</p>, diagnosticsHost)}
    {plan.preview_simplified && <p role="note">预览已简化：显示 {plan.count} / {plan.total_count} 个实例，最终设计参数未改变。</p>}
    {plan.skipped_count > 0 && <p role="note">跳过 {plan.skipped_count} 个没有可靠布点坐标的元素。</p>}
    {plan.unmatched_reference_count > 0 && <p role="note">{plan.unmatched_reference_count} 个元素缺少稳定基准尺寸，单元保持原始大小。</p>}
  </div>
}
