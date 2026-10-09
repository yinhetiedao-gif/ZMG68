import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { requestFabricPreview, type FabricDesignPreview } from '../api/fabricPreview'
import type { PatternDocumentDTO } from '../model/types'
import { useFabricPreview } from './useFabricPreview'

vi.mock('../api/fabricPreview', () => ({ requestFabricPreview: vi.fn() }))

const dto = (revision: number) => ({ document_id: 'fabric', document_revision: revision }) as PatternDocumentDTO
const preview = (revision: number) => ({ document_id: 'fabric', document_revision: revision,
  preview_id: `preview-${revision}` }) as FabricDesignPreview

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

describe('Fabric preview revision lifecycle', () => {
  beforeEach(() => vi.mocked(requestFabricPreview).mockReset())

  it('accepts a matching revision 16 response from the current document', async () => {
    vi.mocked(requestFabricPreview).mockResolvedValue(preview(16))
    const { result } = renderHook(() => useFabricPreview(dto(16)))
    await act(async () => { await result.current.update() })
    expect(requestFabricPreview).toHaveBeenCalledWith(expect.objectContaining({ document_revision: 16 }), expect.any(AbortSignal), fetch)
    expect(result.current.status).toBe('ready')
    expect(result.current.result?.document_revision).toBe(16)
  })

  it('discards a revision 15 response arriving after revision 16', async () => {
    const old = deferred<FabricDesignPreview>()
    const current = deferred<FabricDesignPreview>()
    vi.mocked(requestFabricPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const { result, rerender } = renderHook(({ document }) => useFabricPreview(document), {
      initialProps: { document: dto(15) },
    })
    act(() => { void result.current.update() })
    rerender({ document: dto(16) })
    await waitFor(() => expect(result.current.status).toBe('stale'))
    await act(async () => { old.resolve(preview(15)); await old.promise })
    expect(result.current.result).toBeNull()
    act(() => { void result.current.update() })
    await act(async () => { current.resolve(preview(16)); await current.promise })
    expect(result.current.status).toBe('ready')
    expect(result.current.result?.document_revision).toBe(16)
  })

  it('deduplicates same-frame requests and permits retry after an actual failure', async () => {
    const old = deferred<FabricDesignPreview>()
    const current = deferred<FabricDesignPreview>()
    vi.mocked(requestFabricPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const { result } = renderHook(() => useFabricPreview(dto(16)))
    act(() => { void result.current.update(); void result.current.update() })
    expect(requestFabricPreview).toHaveBeenCalledTimes(1)
    await act(async () => { old.reject(new Error('request failed')); await old.promise.catch(() => undefined) })
    expect(result.current.status).toBe('error')
    act(() => { void result.current.update() })
    await act(async () => { current.resolve(preview(16)); await current.promise })
    expect(result.current.result?.preview_id).toBe('preview-16')
    expect(result.current.status).toBe('ready')
    expect(result.current.error).toBeNull()
  })

  it('automatically coalesces changed revisions to only the latest after the active request drains', async () => {
    const old = deferred<FabricDesignPreview>(), latest = deferred<FabricDesignPreview>()
    vi.mocked(requestFabricPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    const { result, rerender } = renderHook(({ document, busy }) => useFabricPreview(document, fetch, () => busy,
      { automatic: true, blocked: false, computeBusy: busy }), { initialProps: { document: dto(15), busy: false } })
    await waitFor(() => expect(requestFabricPreview).toHaveBeenCalledTimes(1))
    rerender({ document: dto(16), busy: true }); rerender({ document: dto(17), busy: true })
    await act(async () => { old.resolve(preview(15)); await old.promise })
    expect(result.current.result).toBeNull()
    expect(requestFabricPreview).toHaveBeenCalledTimes(1)
    rerender({ document: dto(17), busy: false })
    await waitFor(() => expect(requestFabricPreview).toHaveBeenCalledTimes(2))
    expect(vi.mocked(requestFabricPreview).mock.calls[1][0].document_revision).toBe(17)
    await act(async () => { latest.resolve(preview(17)); await latest.promise })
    expect(result.current.result?.document_revision).toBe(17)
  })

  it('retains the last picture while recalculating but never marks it as the current result', async () => {
    vi.mocked(requestFabricPreview).mockResolvedValueOnce(preview(16))
    const { result, rerender } = renderHook(({ document }) => useFabricPreview(document), { initialProps: { document: dto(16) } })
    await act(async () => { await result.current.update() })
    const next = deferred<FabricDesignPreview>(); vi.mocked(requestFabricPreview).mockReturnValue(next.promise)
    rerender({ document: dto(17) }); act(() => { void result.current.update() })
    expect(result.current.result).toBeNull()
    expect(result.current.displayResult?.document_revision).toBe(16)
    await act(async () => { next.resolve(preview(17)); await next.promise })
    expect(result.current.displayResult?.document_revision).toBe(17)
  })
})
