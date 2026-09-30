import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ManufacturingBuildResult } from '../api/manufacturing'
import { StlExportButton } from './StlExportButton'
import type { ManufacturingStatus } from './useManufacturing'

const result = {
  manufacturing_result_id: 'mesh-current',
  mesh_validation_summary: { error_count: 0 },
} as ManufacturingBuildResult

function show(status: ManufacturingStatus, current: ManufacturingBuildResult | null = result,
  isCurrentResult = () => true) {
  return render(<StlExportButton result={current} status={status} projectName="测试图案.pattern.json"
    isCurrentResult={isCurrentResult} />)
}

describe('shared STL export control', () => {
  it('allows ready and warning results, including multi-component warnings', () => {
    const view = show('ready')
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
    view.rerender(<StlExportButton result={result} status="warning" projectName="测试图案.pattern.json"
      isCurrentResult={() => true} />)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeEnabled()
  })

  it.each(['idle', 'building', 'stale', 'error'] as const)('disables export in %s state', (status) => {
    show(status, status === 'idle' ? null : result)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    expect(screen.getByText(/请先|正在生成|重新检查并生成|检查失败/)).toBeInTheDocument()
  })

  it('rejects missing, invalid-mesh and no-longer-current results', () => {
    const view = show('ready', null)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    view.rerender(<StlExportButton result={{ ...result, mesh_validation_summary: {
      ...result.mesh_validation_summary!, error_count: 1 } }} status="ready"
      projectName={null} isCurrentResult={() => true} />)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    expect(screen.getByText(/Mesh 检查存在错误/)).toBeInTheDocument()
    view.rerender(<StlExportButton result={result} status="ready" projectName={null}
      isCurrentResult={() => false} />)
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
  })

  it('downloads the existing STL route with the project name', async () => {
    const fetcher = vi.fn<typeof fetch>(() => Promise.resolve({ ok: true, status: 200,
      arrayBuffer: async () => new Uint8Array(100).buffer } as Response))
    vi.stubGlobal('fetch', fetcher)
    const createUrl = vi.fn(() => 'blob:stl')
    vi.stubGlobal('URL', { ...URL, createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe('测试图案.stl')
    })
    show('ready')
    fireEvent.click(screen.getByRole('button', { name: '导出 STL' }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(String(fetcher.mock.calls[0][0])).toContain('/api/v1/manufacturing/mesh-current/model.stl')
    expect(createUrl).toHaveBeenCalledOnce()
    click.mockRestore()
  })
})
