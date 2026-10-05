import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { FabricFusionPanel } from './FabricFusionPanel'
import { requestFabricFusion } from '../api/fabricFusion'
import type { PatternDocumentDTO } from '../model/types'

const dto = (revision = 1) => ({ document_id: 'fusion', document_revision: revision }) as PatternDocumentDTO
const report = (revision = 1) => ({ schema_version: '1.0', kind: 'final_fabric_mesh',
  document_id: 'fusion', document_revision: revision, final_fabric_mesh_id: 'fabric-final-test',
  final_fabric_mesh_ready: true, fused: true, export_available: false,
  connected_component_count: 1, watertight: true, volume_mm3: 2560,
  bounds_mm: [[0,0,0],[60,60,3.6]], interface_overlap_mm: 0, cache_hit: false,
  validation_report: { is_watertight: true, finite_coordinates: true,
    error_count: 0, degenerate_face_count: 0, component_count: 1 } })

describe('F5-B readonly final mesh', () => {
  it('uses current DTO once, displays genuine validation and invalidates on commit', async () => {
    const document = dto(); const before = JSON.stringify(document)
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(report())))
    const { rerender } = render(<FabricFusionPanel document={document} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '生成最终制造网格' }))
    await screen.findByText('最终网格已通过检查')
    expect(screen.getByText(/Components: 1/)).toBeTruthy()
    expect(screen.getByText(/60.00 × 60.00 × 3.60/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /下载|导出/ })).toBeNull()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(JSON.parse(fetcher.mock.calls[0][1].body).document).toEqual(document)
    expect(JSON.stringify(document)).toBe(before)
    rerender(<FabricFusionPanel document={dto(2)} fetcher={fetcher} />)
    expect(screen.queryByText('最终网格已通过检查')).toBeNull()
    expect(screen.getByText('设计已变化，请重新生成最终制造网格。')).toBeTruthy()
  })
  it('discards late old results and allows a fresh request', async () => {
    let resolve!: (r: Response) => void
    const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>(yes => { resolve = yes }))
      .mockResolvedValueOnce(new Response(JSON.stringify(report(2))))
    const { rerender } = render(<FabricFusionPanel document={dto()} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '生成最终制造网格' }))
    rerender(<FabricFusionPanel document={dto(2)} fetcher={fetcher} />)
    await act(async () => resolve(new Response(JSON.stringify(report()))))
    expect(screen.queryByText('最终网格已通过检查')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '生成最终制造网格' }))
    await screen.findByText('最终网格已通过检查')
  })
  it('shows failure stage and ID without a success or download', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { message: '存在未连接单元' }, fusion_report: { stage: 'preflight', failure_id: 'failure-1' },
    }), { status: 422 }))
    render(<FabricFusionPanel document={dto()} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '生成最终制造网格' }))
    expect((await screen.findByRole('alert')).textContent).toContain('preflight；失败编号：failure-1')
    expect(screen.queryByText('最终网格已通过检查')).toBeNull()
  })
  it('rejects mismatched, weak validation, invalid bounds and export-enabled responses', async () => {
    for (const result of [{}, { ...report(), document_revision: 2 },
      { ...report(), connected_component_count: 2 }, { ...report(), export_available: true },
      { ...report(), validation_report: { ...report().validation_report, degenerate_face_count: 1 } },
      { ...report(), bounds_mm: [[0,0,0],[60,60,null]] }]) {
      await expect(requestFabricFusion(dto(), undefined,
        vi.fn().mockResolvedValue(new Response(JSON.stringify(result))))).rejects.toThrow(/不匹配/)
    }
  })
})
