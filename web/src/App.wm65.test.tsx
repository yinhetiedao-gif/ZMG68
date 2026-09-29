import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function reply(value: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => value } as Response
}

function backend(recommended: 'grid' | null = 'grid', failFamily?: string) {
  const elements = Array.from({ length: 36 }, (_, index) => ({
    id: `dot-${index}`, type: 'circle', x: 10 + index % 6 * 10,
    y: 10 + Math.floor(index / 6) * 10, width: 4, height: 4,
    rotation: 0, visible: true, style: { fill: '#000' },
  }))
  const dto = { schema_version: '1.0', document_id: 'imported', document_revision: 0,
    document: { schema_version: 1, canvas: { width: 80, height: 80, unit: 'mm', mm_per_unit: 1 },
      reference: { source_path: '', visible: false }, elements, groups: [], transforms: {},
      metadata: {}, fields: [], modifiers: [] }, assets: [] }
  const calls: { path: string; body: Record<string, unknown> }[] = []
  const mock = vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    const body = init?.body && !path.endsWith('/assets')
      ? JSON.parse(String(init.body)) as Record<string, unknown> : {}
    calls.push({ path, body })
    if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    if (path.endsWith('/assets')) return Promise.resolve(reply({ asset_id: 'imported' }))
    if (path.endsWith('/import')) return Promise.resolve(reply(dto))
    if (path.endsWith('/analyze-pattern')) {
      const request = body.document as typeof dto
      return Promise.resolve(reply({ document_id: request.document_id,
        document_revision: request.document_revision, recommended_family: recommended,
        confidence: recommended === 'grid' ? .95 : 0,
        analysis_status: recommended ? 'matched' : 'no_match' }))
    }
    if (path.endsWith('/apply-pattern')) {
      if (body.family === failFamily) return Promise.resolve(reply({ message: '无法应用该图案结构：未找到稳定格点。' }, 422))
      const request = body.document as typeof dto
      return Promise.resolve(reply({ ...request, document_revision: request.document_revision + 1,
        document: { ...request.document, metadata: { 'xiaomang_pattern_lab.parametric': {
          family: body.family === 'free' ? 'free_parametric' : body.family,
        } } } }))
    }
    const request = body.document as typeof dto
    return Promise.resolve(reply({ schema_version: '1.0', document_id: request.document_id,
      document_revision: request.document_revision,
      geometry: request.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 8, min_y: 8, max_x: 62, max_y: 62, width: 54, height: 54, units: 'mm' }, warnings: [] }))
  })
  vi.stubGlobal('fetch', mock)
  return calls
}

async function importSvg() {
  render(<App />)
  await screen.findByText('Backend Online')
  fireEvent.drop(screen.getByLabelText('中央工作区').querySelector('.canvas-stage')!, {
    dataTransfer: { files: [new File(['<svg/>'], 'dots.svg', { type: 'image/svg+xml' })] },
  })
  await screen.findByRole('img', { name: '最终二维几何，单位毫米' })
}

describe('WM6.5 Web pattern structure bridge', () => {
  it('keeps structures usable before analysis and marks the Python recommendation', async () => {
    const calls = backend()
    await importSvg()
    const grid = await screen.findByRole('button', { name: /规则矩阵 Grid/ })
    expect(grid).toBeEnabled()
    expect(screen.getByRole('button', { name: '放射 Radial' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '曲线 Curve' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '自由布局 Free' })).toBeEnabled()
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
    fireEvent.click(grid)
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/apply-pattern'))).toHaveLength(1)
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(2)
    expect(calls.filter((item) => item.path.endsWith('/analyze-pattern')).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('img', { name: '最终二维几何，单位毫米' }).querySelectorAll('[data-element-id]')).toHaveLength(36)
  })

  it('keeps all structures usable without a recommendation; failed apply is explicit', async () => {
    const calls = backend(null, 'grid')
    await importSvg()
    await waitFor(() => expect(screen.getByRole('button', { name: '自由布局 Free' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '规则矩阵 Grid' })).toBeEnabled()
    await screen.findByText('暂无可靠推荐；可手动尝试图案结构。')
    fireEvent.click(screen.getByRole('button', { name: '规则矩阵 Grid' }))
    await screen.findByText('无法应用该图案结构：未找到稳定格点。')
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '自由布局 Free' }))
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/apply-pattern'))).toHaveLength(2)
  })

  it('keeps structure buttons enabled while analysis is still running', async () => {
    const calls = backend()
    const previous = globalThis.fetch
    let finishAnalysis: ((value: Response) => void) | undefined
    vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
      if (String(url).endsWith('/analyze-pattern')) {
        return new Promise<Response>((resolve) => { finishAnalysis = resolve })
      }
      return previous(url, init)
    }))
    await importSvg()
    await screen.findByText('正在分析图案；结构仍可尝试使用。')
    expect(screen.getByRole('button', { name: '规则矩阵 Grid' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '放射 Radial' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '曲线 Curve' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '自由布局 Free' })).toBeEnabled()
    expect(calls.filter((item) => item.path.endsWith('/apply-pattern'))).toHaveLength(0)
    finishAnalysis?.(reply({ document_id: 'imported', document_revision: 0,
      recommended_family: 'grid', confidence: .9, analysis_status: 'matched' }))
    await screen.findByText('推荐：规则矩阵 Grid（90%）')
  })

  it('marks analysis stale on edit, then debounces one refresh without disabling structures', async () => {
    const calls = backend()
    await importSvg()
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
    const canvas = screen.getByRole('img', { name: '最终二维几何，单位毫米' })
    fireEvent.pointerDown(canvas.querySelector('[data-element-id="dot-0"]')!, { button: 0 })
    const width = screen.getByRole('spinbutton', { name: '宽度 mm' })
    fireEvent.change(width, { target: { value: '6' } })
    fireEvent.blur(width)
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    await screen.findByText('图案已修改，推荐结果待更新；结构仍可使用。')
    expect(screen.getByRole('button', { name: '规则矩阵 Grid' })).toBeEnabled()
    expect(calls.filter((item) => item.path.endsWith('/analyze-pattern'))).toHaveLength(1)
    const nextWidth = screen.getByRole('spinbutton', { name: '宽度 mm' })
    fireEvent.change(nextWidth, { target: { value: '7' } })
    fireEvent.blur(nextWidth)
    await waitFor(() => expect(screen.getByText('revision 2')).toBeInTheDocument())
    await waitFor(() => expect(calls.filter((item) => item.path.endsWith('/analyze-pattern'))).toHaveLength(2), {
      timeout: 1500,
    })
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(3)
  })
})
