import { useEffect, useRef, useState } from 'react'
import { AmbientLight, Box3, BufferGeometry, Color, DirectionalLight, DoubleSide, Float32BufferAttribute,
  Group, InstancedMesh, Matrix4, Mesh, MeshPhongMaterial, PerspectiveCamera, Scene, Vector3, WebGLRenderer } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { fetchFabricPlan, fetchPreviewGlb } from '../api/manufacturingArtifacts'

interface Props { resultId: string }

export function ThreePreview({ resultId }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fitRef = useRef<(() => void) | null>(null)
  const resetRef = useRef<(() => void) | null>(null)
  const [status, setStatus] = useState('正在载入最终制造网格…')
  const [bounds, setBounds] = useState<string | null>(null)
  const [instanceCount, setInstanceCount] = useState<number | null>(null)

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    if (!host || !canvas) return
    const abort = new AbortController()
    let disposed = false
    let frame = 0
    let renderer: WebGLRenderer | null = null
    let controls: OrbitControls | null = null
    let observer: ResizeObserver | null = null
    let model: Group | null = null
    const displayMaterial = new MeshPhongMaterial({ color: 0x3a4953, shininess: 25 })
    const instanceMaterial = new MeshPhongMaterial({ color: 0x557c91, shininess: 25, side: DoubleSide })
    const scene = new Scene()
    scene.background = new Color(0xf9fbfc)
    const camera = new PerspectiveCamera(45, 1, 0.01, 100000)
    camera.up.set(0, 0, 1) // The manufacturing extrusion axis stays Z-up.
    scene.add(new AmbientLight(0xffffff, 2.2))
    const light = new DirectionalLight(0xffffff, 2.8)
    light.position.set(1, -2, 3)
    scene.add(light)

    const start = async () => {
      try {
        renderer = new WebGLRenderer({ canvas, antialias: true })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
        controls = new OrbitControls(camera, canvas)
        controls.enableDamping = true
        const resize = () => {
          if (!renderer) return
          const width = Math.max(1, host.clientWidth)
          const height = Math.max(1, host.clientHeight)
          camera.aspect = width / height
          camera.updateProjectionMatrix()
          renderer.setSize(width, height, false)
        }
        resize()
        observer = new ResizeObserver(resize)
        observer.observe(host)
        const bytes = await fetchPreviewGlb(resultId, abort.signal)
        if (disposed) return
        const gltf = await new GLTFLoader().parseAsync(bytes, '')
        if (disposed) return
        model = gltf.scene
        model.traverse((node) => { if (node instanceof Mesh) node.material = displayMaterial })
        let planError: string | null = null
        let planCount: number | null = null
        try {
          const plan = await fetchFabricPlan(resultId, abort.signal)
          if (disposed) return
          if (plan) {
            const geometry = new BufferGeometry()
            geometry.setAttribute('position', new Float32BufferAttribute(plan.prototype.vertices.flat(), 3))
            geometry.setIndex(plan.prototype.faces.flat())
            geometry.computeVertexNormals()
            const instances = new InstancedMesh(geometry, instanceMaterial, plan.count)
            const matrix = new Matrix4()
            plan.instances.forEach((instance, index) => {
              matrix.makeTranslation(instance.x_mm, instance.y_mm, instance.z_mm)
              instances.setMatrixAt(index, matrix)
            })
            instances.instanceMatrix.needsUpdate = true
            instances.computeBoundingSphere()
            model.add(instances)
            planCount = plan.count
            setInstanceCount(plan.count)
          }
        } catch (error) {
          if (abort.signal.aborted || disposed) return
          planError = error instanceof Error ? error.message : 'Unit Cell 预览无法载入。'
        }
        scene.add(model)
        const box = new Box3().setFromObject(model)
        if (box.isEmpty()) throw new Error('GLB 不包含可显示的制造网格。')
        const center = box.getCenter(new Vector3())
        const size = box.getSize(new Vector3())
        setBounds(`${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} mm`)
        const fit = (resetOrientation: boolean) => {
          const maxSize = Math.max(size.x, size.y, size.z, 1)
          const distance = (maxSize / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 1.8
          const direction = resetOrientation ? new Vector3(1, -1, 0.8).normalize()
            : camera.position.clone().sub(controls!.target).normalize()
          if (direction.lengthSq() < 0.01) direction.set(1, -1, 0.8).normalize()
          camera.near = Math.max(0.001, distance / 1000)
          camera.far = distance * 1000
          camera.position.copy(center).addScaledVector(direction, distance)
          camera.updateProjectionMatrix()
          controls!.target.copy(center)
          controls!.update()
        }
        fitRef.current = () => fit(false)
        resetRef.current = () => fit(true)
        fit(true)
        setStatus(planError ?? (planCount === null ? '三维预览已就绪 · 鼠标拖动旋转，滚轮缩放'
          : '基底 + Unit Cell 设计预览已就绪；STL 仍只包含基底。'))
        const animate = () => {
          if (disposed || !renderer || !controls) return
          frame = requestAnimationFrame(animate)
          controls.update()
          renderer.render(scene, camera)
        }
        animate()
      } catch (error) {
        if (!disposed && !abort.signal.aborted) setStatus(error instanceof Error ? error.message : '三维预览载入失败。')
      }
    }
    void start()
    return () => {
      disposed = true
      abort.abort()
      cancelAnimationFrame(frame)
      observer?.disconnect()
      controls?.dispose()
      model?.traverse((node) => { if (node instanceof Mesh) node.geometry.dispose() })
      displayMaterial.dispose()
      instanceMaterial.dispose()
      renderer?.dispose()
      fitRef.current = null
      resetRef.current = null
    }
  }, [resultId])

  return <div className="three-preview" aria-label="三维模型预览">
    <div className="three-preview-toolbar"><button type="button" onClick={() => fitRef.current?.()} disabled={!bounds}>适合窗口</button>
      <button type="button" onClick={() => resetRef.current?.()} disabled={!bounds}>重置视角</button></div>
    <div className="three-preview-viewport" ref={hostRef}><canvas ref={canvasRef} aria-label="最终制造网格三维画布" /></div>
    <div className="three-preview-status" role="status">{status}</div>
    {bounds && <small className="three-preview-bounds">预览 XYZ：{bounds}</small>}
    {instanceCount !== null && <small className="three-preview-bounds" data-instance-count={instanceCount}>
      Unit Cell：{instanceCount} 个共享原型实例；仅设计预览，不包含在当前 STL 中。</small>}
  </div>
}
