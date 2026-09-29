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
        metadata: {}, fields: [], modifiers: [] }, assets: [] }
    const fetcher = vi.fn<typeof fetch>((url) => {
      const path = String(url)
      if (path.endsWith('/health')) return Promise.resolve(reply({ status: 'ok', contract_version: '1.0' }))
      if (path.endsWith('/contract')) return Promise.resolve(reply({ schema_version: '1.0', units: 'mm' }))
      if (path.endsWith('/assets')) return Promise.resolve(reply({ asset_id: 'asset-1' }))
      if (path.endsWith('/import')) return Promise.resolve(reply(dto))
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
  })
})
