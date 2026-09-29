import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function reply(value: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => value } as Response
}

function backend(recommended: 'grid' | null = 'grid', failAction?: string) {
  const elements = Array.from({ length: 36 }, (_, index) => ({
    id: `dot-${index}`, type: 'circle', x: 10 + index % 6 * 10,
    y: 10 + Math.floor(index / 6) * 10, width: 4, height: 4,
    rotation: 0, visible: true, style: { fill: '#000' },
  }))
  const dto = { schema_version: '1.0', document_id: 'imported', document_revision: 0,
    document: { schema_version: 1, canvas: { width: 80, height: 80, unit: 'mm', mm_per_unit: 1 },
      reference: { source_path: '', visible: false }, elements, groups: [], transforms: {},
      metadata: {} as Record<string, unknown>, fields: [], modifiers: [] }, assets: [] }
  const calls: { path: string; body: Record<string, unknown> }[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
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
        confidence: recommended ? .95 : 0, analysis_status: recommended ? 'matched' : 'no_match' }))
    }
    if (path.endsWith('/pattern-action')) {
      if (body.action === failAction) return Promise.resolve(reply({ message: '当前没有可靠的推荐结构。' }, 422))
      const request = body.document as typeof dto
      const metadata = { ...request.document.metadata }
      if (body.action === 'bake') delete metadata['xiaomang_pattern_lab.parametric']
      else metadata['xiaomang_pattern_lab.parametric'] = { family: body.action === 'enter_free' ? 'free_parametric' : 'grid' }
      return Promise.resolve(reply({ ...request, document_revision: request.document_revision + 1,
        document: { ...request.document, metadata } }))
    }
    const request = body.document as typeof dto
    return Promise.resolve(reply({ schema_version: '1.0', document_id: request.document_id,
      document_revision: request.document_revision,
      geometry: request.document.elements.map((element) => ({ ...element, units: 'mm' })),
      bounds_mm: { min_x: 8, min_y: 8, max_x: 62, max_y: 62, width: 54, height: 54, units: 'mm' }, warnings: [] }))
  }))
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

describe('Web/Desktop parameterization semantics', () => {
  it('imports without rearrangement; family selection and Try only analyze', async () => {
    const calls = backend()
    await importSvg()
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
    for (const label of ['规则矩阵 Grid', '放射 Radial', '曲线 Curve', '自由布局 Free']) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }))
    }
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    expect(calls.filter((item) => item.path.endsWith('/pattern-action'))).toHaveLength(0)
    expect(calls.filter((item) => item.path.endsWith('/prepare-pattern'))).toHaveLength(0)
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '尝试参数化' }))
    await waitFor(() => expect(calls.filter((item) => item.path.endsWith('/analyze-pattern'))).toHaveLength(2))
    expect(screen.getByText('revision 0')).toBeInTheDocument()
  })

  it('converts only on explicit recommendation action; one commit and evaluate', async () => {
    const calls = backend()
    await importSvg()
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
    fireEvent.click(screen.getByRole('button', { name: '放射 Radial' }))
    fireEvent.click(screen.getByRole('button', { name: '转换为推荐结构' }))
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/pattern-action')).map((item) => item.body.action))
      .toEqual(['convert_recommended'])
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(2)
  })

  it('enters Free without a recommendation and can bake', async () => {
    const calls = backend(null)
    await importSvg()
    await screen.findByText('暂无可靠推荐；可手动尝试图案结构。')
    expect(screen.getByRole('button', { name: '转换为推荐结构' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '进入自由参数化' }))
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(screen.getByRole('img', { name: '最终二维几何，单位毫米' }).querySelectorAll('[data-element-id]')).toHaveLength(36)
    fireEvent.click(screen.getByRole('button', { name: '烘焙为自由元素' }))
    await waitFor(() => expect(screen.getByText('revision 2')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/pattern-action')).map((item) => item.body.action))
      .toEqual(['enter_free', 'bake'])
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(3)
  })

  it('keeps the document and geometry when a conversion fails', async () => {
    const calls = backend('grid', 'convert_recommended')
    await importSvg()
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
    fireEvent.click(screen.getByRole('button', { name: '转换为推荐结构' }))
    await screen.findByText('当前没有可靠的推荐结构。')
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(1)
  })

  it('keeps candidate selection available during automatic analysis', async () => {
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
    fireEvent.click(screen.getByRole('button', { name: '放射 Radial' }))
    expect(screen.getByText('revision 0')).toBeInTheDocument()
    expect(calls.filter((item) => item.path.endsWith('/pattern-action'))).toHaveLength(0)
    finishAnalysis?.(reply({ document_id: 'imported', document_revision: 0,
      recommended_family: 'grid', confidence: .95, analysis_status: 'matched' }))
    await screen.findByText('推荐：规则矩阵 Grid（95%）')
  })

  it('debounces analysis after a normal element edit without changing candidate availability', async () => {
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
    expect(screen.getByRole('button', { name: '放射 Radial' })).toBeEnabled()
    await waitFor(() => expect(calls.filter((item) => item.path.endsWith('/analyze-pattern'))).toHaveLength(2), {
      timeout: 1500,
    })
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(2)
  })
})
