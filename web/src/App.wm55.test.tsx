import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

function reply(value: unknown): Response {
  return { ok: true, status: 200, json: async () => value } as Response
}

describe('WM5.5 browser import', () => {
  it('accepts a dropped SVG and displays its Python-evaluated element', async () => {
    const element = { id: 'dot', type: 'circle', x: 10, y: 10, width: 5, height: 5,
      rotation: 0, visible: true, style: { fill: '#000' } }
    const dto = { schema_version: '1.0', document_id: 'asset-1', document_revision: 0,
      document: { schema_version: 1, canvas: { width: 20, height: 20, unit: 'mm', mm_per_unit: 1 },
        reference: { source_path: '', visible: false }, elements: [element], groups: [], transforms: {},
        metadata: { web_import_scale_unconfirmed: true }, fields: [], modifiers: [] }, assets: [] }
    const fetcher = vi.fn<typeof fetch>((url, init) => {
      const path = String(url)
      if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
      if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
      if (path.endsWith('/assets')) return Promise.resolve(reply({ asset_id: 'asset-1' }))
      if (path.endsWith('/import')) return Promise.resolve(reply(dto))
      if (path.endsWith('/manufacturing/build')) {
        const request = JSON.parse(String(init?.body)) as { document_revision: number; height_mm: number }
        return Promise.resolve(reply({ schema_version: '1.0', status: 'completed', manufacturing_result_id: 'mesh-import',
          document_id: dto.document_id, document_revision: request.document_revision,
          geometry_validation_summary: { checked_count: 1, error_count: 0, warning_count: 0, issues: [] },
          connectivity_summary: { component_count: 1, isolated_count: 0 },
          conversion_summary: { input_count: 1, converted_count: 1, skipped_count: 0, warnings: [] },
          mesh_validation_summary: { is_watertight: true, component_count: 1, error_count: 0, warning_count: 0, issues: [] },
          component_count: 1, bounds_mm: { size_x: 5, size_y: 5, size_z: request.height_mm, units: 'mm' }, warnings: [],
        }))
      }
      if (path.endsWith('/model.stl')) return Promise.resolve({ ok: true, status: 200,
        arrayBuffer: async () => new Uint8Array(100).buffer } as Response)
      return Promise.resolve(reply({ schema_version: '1.0', document_id: 'asset-1', document_revision: 0,
        geometry: [{ ...element, units: 'mm' }], bounds_mm: { min_x: 7.5, min_y: 7.5,
          max_x: 12.5, max_y: 12.5, width: 5, height: 5, units: 'mm' }, warnings: [] }))
    })
    vi.stubGlobal('fetch', fetcher)
    render(<App />)
    await screen.findByText('Backend Online')
    const file = new File(['<svg/>'], 'test.svg', { type: 'image/svg+xml' })
    fireEvent.drop(screen.getByLabelText('中央工作区').querySelector('.canvas-stage')!, {
      dataTransfer: { files: [file] },
    })
    await waitFor(() => expect(screen.getByLabelText('最终二维几何，单位毫米')).toBeInTheDocument())
    expect(screen.getByText(/1 个元素/)).toBeInTheDocument()
    expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(expect.arrayContaining([
      expect.stringMatching(/\/api\/v1\/assets$/), expect.stringMatching(/\/api\/v1\/import$/),
      expect.stringMatching(/\/api\/v1\/evaluate$/),
    ]))
    expect(screen.getByText(/制造前必须确认真实尺寸/)).toHaveClass('viewer-warning')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    const note = screen.getByRole('note')
    const actions = screen.getByRole('button', { name: '导出 STL' }).closest('.manufacturing-output-actions')!
    expect(note).toHaveClass('manufacturing-notes')
    expect(note.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(document.querySelector('.viewer-warning')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '检查并生成' }))
    expect(await screen.findByText('模型已生成')).toBeInTheDocument()
    const createUrl = vi.fn(() => 'blob:stl')
    vi.stubGlobal('URL', { ...URL, createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    fireEvent.click(screen.getByRole('button', { name: '导出 STL' }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(fetcher.mock.calls.map(([url]) => String(url))).toContainEqual(expect.stringMatching(/\/model\.stl$/))
    click.mockRestore()
  })
})
