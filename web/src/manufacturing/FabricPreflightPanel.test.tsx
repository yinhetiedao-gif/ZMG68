import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { FabricPreflightPanel } from './FabricPreflightPanel'
import { requestFabricCandidate } from '../api/fabricCandidate'
import type { PatternDocumentDTO } from '../model/types'

const dto = (revision = 1) => ({ document_id: 'test', document_revision: revision }) as PatternDocumentDTO
const report = (revision = 1) => ({ schema_version: '1.0', kind: 'fabric_manufacturing_candidate',
  document_id: 'test', document_revision: revision, status: 'checked', fused: false, export_available: false,
  instance_count: 1, enabled_instance_count: 1, bounds_mm: [[0,0,0],[60,60,3.6]],
  attachment_counts: { ATTACHED: 1, MARGINAL: 0, DETACHED: 0, INVALID: 0 },
  attachments: [{ instance_id: 'cell', status: 'ATTACHED', contact_area_mm2: 4, issues: [] }], issues: [] })

describe('F5-A read-only preflight', () => {
  it('shows contact, not fusion; revision changes invalidate the report', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(report())))
    const before = JSON.stringify(dto())
    const { rerender } = render(<FabricPreflightPanel document={dto()} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '检查可制造性' }))
    await screen.findByText('预检完成（未融合）')
    expect(screen.getByText(/接触到底布：1/)).toBeTruthy()
    expect(screen.getByText(/60.00 × 60.00 × 3.60/)).toBeTruthy()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(JSON.stringify(dto())).toBe(before)
    rerender(<FabricPreflightPanel document={dto(2)} fetcher={fetcher} />)
    expect(screen.getByText('设计已变化，请重新检查可制造性。')).toBeTruthy()
    expect(screen.queryByText(/接触到底布：1/)).toBeNull()
  })
  it('discards a late stale response', async () => {
    let resolve!: (response: Response) => void
    const fetcher = vi.fn().mockReturnValue(new Promise<Response>(yes => { resolve = yes }))
    const { rerender } = render(<FabricPreflightPanel document={dto()} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '检查可制造性' }))
    rerender(<FabricPreflightPanel document={dto(2)} fetcher={fetcher} />)
    await act(async () => resolve(new Response(JSON.stringify(report()))))
    expect(screen.queryByText('预检完成（未融合）')).toBeNull()
  })
  it('reports API errors without export or document mutation', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: '单元参数非法' } }), { status: 400 }))
    render(<FabricPreflightPanel document={dto()} fetcher={fetcher} />)
    fireEvent.click(screen.getByRole('button', { name: '检查可制造性' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('单元参数非法'))
  })
  it('rejects mismatched identity and missing or fused contracts', async () => {
    for (const data of [{ ...report(), document_revision: 2 }, { ...report(), fused: true }, {}]) {
      await expect(requestFabricCandidate(dto(), undefined,
        vi.fn().mockResolvedValue(new Response(JSON.stringify(data))))).rejects.toThrow(/不匹配/)
    }
  })
})
