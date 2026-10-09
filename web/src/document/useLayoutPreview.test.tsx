import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useLayoutPreview, useDocumentPreview } from './useLayoutPreview'
import { createBlankDesign } from './nativeDesign'
import { evaluateDocument } from '../api/evaluate'
import type { EvaluateResponse } from '../model/types'
vi.mock('../api/evaluate', () => ({ evaluateDocument: vi.fn() }))

describe('unapplied Python layout preview', () => {
  it('continuous pointer input cannot postpone authority requests indefinitely; bounded single latest slot', async () => {
    vi.useFakeTimers()
    try {
      const dto = createBlankDesign('continuous'), responses: ((value: EvaluateResponse) => void)[] = []
      vi.mocked(evaluateDocument).mockImplementation(() => new Promise(resolve => responses.push(resolve)))
      const hook = renderHook(({ revision }) => useDocumentPreview({ ...dto, document_revision: revision }, fetch), { initialProps: { revision: 0 } })
      for (let n = 1; n <= 10; n++) {
        await act(async () => { await vi.advanceTimersByTimeAsync(30) })
        hook.rerender({ revision: n })
      }
      expect(responses).toHaveLength(1)
      await act(async () => responses[0]({ geometry: [] } as unknown as EvaluateResponse))
      expect(hook.result.current.result).toBeNull()
      await act(async () => { await vi.advanceTimersByTimeAsync(180) })
      expect(responses).toHaveLength(2)
      expect(vi.mocked(evaluateDocument).mock.calls.at(-1)?.[0].document_revision).toBe(10)
      hook.unmount()
    } finally { vi.useRealTimers() }
  })
  it('retains last valid picture on candidate failure, without allowing failed input to Apply', async () => {
    const dto = createBlankDesign('candidate'), result = { geometry: [] } as unknown as EvaluateResponse
    vi.mocked(evaluateDocument).mockResolvedValueOnce(result).mockRejectedValueOnce(new Error('bad input'))
    const hook = renderHook(({ revision }) => useDocumentPreview({ ...dto, document_revision: revision }, fetch), { initialProps: { revision: 0 } })
    await waitFor(() => expect(hook.result.current.result).toBe(result))
    hook.rerender({ revision: 1 })
    await waitFor(() => expect(hook.result.current.error).toBe('bad input'))
    expect(hook.result.current.result).toBeNull(); expect(hook.result.current.displayResult).toBe(result)
  })
  it('reuses preparation preview and only evaluates changed parameters', async () => {
    const dto = createBlankDesign('layout'), preview = { geometry: [] } as unknown as EvaluateResponse
    const seed = { key: JSON.stringify(dto), result: preview }
    const hook = renderHook(({ proposal }) => useLayoutPreview({ family: 'grid', proposal, sourceRevision: 0, changed: true }, true, fetch, seed), { initialProps: { proposal: dto } })
    expect(hook.result.current.result).toBe(preview); expect(evaluateDocument).not.toHaveBeenCalled()
    vi.mocked(evaluateDocument).mockResolvedValue(preview)
    hook.rerender({ proposal: { ...dto, document_revision: 1 } })
    await waitFor(() => expect(evaluateDocument).toHaveBeenCalledOnce())
    expect(dto.document_revision).toBe(0)
  })
  it('drains one active request, coalesces latest input and discards old results or cancellation', async () => {
    const dto = createBlankDesign('layout'); const responses: ((v: EvaluateResponse) => void)[] = []
    vi.mocked(evaluateDocument).mockImplementation(() => new Promise(resolve => responses.push(resolve)))
    const hook = renderHook(({ revision, enabled }) => useLayoutPreview({ family: 'grid', proposal: { ...dto, document_revision: revision }, sourceRevision: 0, changed: true }, enabled, fetch, null), { initialProps: { revision: 1, enabled: true } })
    await waitFor(() => expect(responses).toHaveLength(1))
    hook.rerender({ revision: 2, enabled: true }); hook.rerender({ revision: 3, enabled: true })
    expect(responses).toHaveLength(1)
    await act(async () => responses[0]({ document_revision: 1 } as EvaluateResponse))
    expect(hook.result.current.result).toBeNull()
    await waitFor(() => expect(responses).toHaveLength(2))
    hook.rerender({ revision: 3, enabled: false })
    await act(async () => responses[1]({ document_revision: 3 } as EvaluateResponse))
    expect(hook.result.current.result).toBeNull()
    expect(vi.mocked(evaluateDocument).mock.calls.at(-1)?.[0].document_revision).toBe(3)
  })
})
