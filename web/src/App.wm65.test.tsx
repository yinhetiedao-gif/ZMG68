import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function reply(value: unknown): Response {
  return { ok: true, status: 200, json: async () => value } as Response
}

function backend(recommended: 'grid' | 'free' = 'grid') {
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
        document_revision: request.document_revision, recommended, warnings: [], families: [
          { id: 'grid', confidence: recommended === 'grid' ? .95 : 0, available: recommended === 'grid', parameters: {}, reason: '' },
          { id: 'radial', confidence: 0, available: false, parameters: {}, reason: '不符合放射结构' },
          { id: 'along_curve', confidence: 0, available: false, parameters: {}, reason: '' },
          { id: 'free', confidence: 1, available: true, parameters: {}, reason: '' },
        ] }))
    }
    if (path.endsWith('/apply-pattern')) {
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
  it('analyzes imported geometry and applies Grid with one revision and one evaluate', async () => {
    const calls = backend()
    await importSvg()
    const grid = await screen.findByRole('button', { name: '规则矩阵 Grid' })
    await waitFor(() => expect(grid).toBeEnabled())
    expect(screen.getByRole('button', { name: '放射 Radial' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '自由布局 Free' })).toBeEnabled()
    fireEvent.click(grid)
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/apply-pattern'))).toHaveLength(1)
    expect(calls.filter((item) => item.path.endsWith('/evaluate'))).toHaveLength(2)
    expect(calls.filter((item) => item.path.endsWith('/analyze-pattern')).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('img', { name: '最终二维几何，单位毫米' }).querySelectorAll('[data-element-id]')).toHaveLength(36)
  })

  it('keeps Free available when structured recognition fails', async () => {
    const calls = backend('free')
    await importSvg()
    await waitFor(() => expect(screen.getByRole('button', { name: '自由布局 Free' })).toBeEnabled())
    expect(screen.getByRole('button', { name: '规则矩阵 Grid' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '自由布局 Free' }))
    await waitFor(() => expect(screen.getByText('revision 1')).toBeInTheDocument())
    expect(calls.filter((item) => item.path.endsWith('/apply-pattern'))).toHaveLength(1)
  })
})
