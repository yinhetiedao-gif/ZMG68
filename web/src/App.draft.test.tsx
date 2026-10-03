import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { loadDraft } from './draft/localDraft'

function reply(value: unknown): Response {
  return { ok: true, status: 200, json: async () => value } as Response
}

const element = { id: 'dot', type: 'circle', x: 10, y: 10, width: 5, height: 5,
  rotation: 0, visible: true, style: { fill: '#000' } }
const dto = { schema_version: '1.0', document_id: 'imported-draft', document_revision: 4,
  document: { schema_version: 1, canvas: { width: 60, height: 60, unit: 'mm', mm_per_unit: 1 },
    reference: {}, elements: [element], groups: [], transforms: {},
    metadata: { fabric_config: { base: { type: 'grid' } },
      'xiaomang_pattern_lab.parametric': { family: 'grid' } },
    fields: [{ id: 'wave-1', type: 'wave', parameters: { wavelength: 10 } }],
    modifiers: [{ id: 'size-1', type: 'size', field_id: 'wave-1' }] }, assets: [] }

function backend() {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>((url, init) => {
    const path = String(url)
    paths.push(path)
    if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
    if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
    if (path.endsWith('/assets')) return Promise.resolve(reply({ asset_id: 'asset-1' }))
    if (path.endsWith('/import')) return Promise.resolve(reply(dto))
    const body = JSON.parse(String(init?.body)) as { document: typeof dto }
    if (path.endsWith('/analyze-pattern')) return Promise.resolve(reply({ document_id: body.document.document_id,
      document_revision: body.document.document_revision, recommended_family: 'grid', confidence: .96,
      analysis_status: 'matched' }))
    return Promise.resolve(reply({ schema_version: '1.0', document_id: body.document.document_id,
      document_revision: body.document.document_revision, geometry: [{ ...element, units: 'mm' }],
      bounds_mm: { min_x: 7.5, min_y: 7.5, max_x: 12.5, max_y: 12.5, width: 5, height: 5, units: 'mm' }, warnings: [] }))
  }))
  return paths
}

describe('browser local draft recovery', () => {
  it.each(['image/png', 'image/svg+xml'])('restores imported %s canonical design after a refresh', async (type) => {
    const paths = backend()
    const view = render(<App />)
    await screen.findByText('Backend Online')
    const file = new File(['fixture'], type === 'image/png' ? 'dots.png' : 'dots.svg', { type })
    fireEvent.drop(screen.getByLabelText('中央工作区').querySelector('.canvas-stage')!, {
      dataTransfer: { files: [file] },
    })
    await screen.findByLabelText('最终二维几何，单位毫米')
    await waitFor(async () => expect((await loadDraft())?.dto).toEqual(dto), { timeout: 3000 })
    const saved = await loadDraft()
    expect(saved?.file_name).toBe(file.name)
    expect(saved?.source_asset?.filename).toBe(file.name)
    expect(saved?.dto.document.metadata.fabric_config).toEqual(dto.document.metadata.fabric_config)
    const evaluationsBefore = paths.filter((path) => path.endsWith('/evaluate')).length
    view.unmount()
    render(<App />)
    await screen.findByRole('region', { name: '恢复上次编辑' })
    expect(screen.queryByLabelText('最终二维几何，单位毫米')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '恢复上次编辑' }))
    await screen.findByLabelText('最终二维几何，单位毫米')
    expect(paths.filter((path) => path.endsWith('/evaluate'))).toHaveLength(evaluationsBefore + 1)
    expect(screen.getByLabelText('当前项目')).toHaveTextContent(file.name)
  })
})
