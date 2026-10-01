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
    expect(requestFabricPreview).toHaveBeenCalledWith(expect.objectContaining({ document_revision: 16 }), expect.any(AbortSignal))
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
    act(() => { old.resolve(preview(15)) })
    expect(result.current.result).toBeNull()
    act(() => { void result.current.update() })
    await act(async () => { current.resolve(preview(16)); await current.promise })
    expect(result.current.status).toBe('ready')
    expect(result.current.result?.document_revision).toBe(16)
  })

  it('only accepts the latest request even when the revision is unchanged', async () => {
    const old = deferred<FabricDesignPreview>()
    const current = deferred<FabricDesignPreview>()
    vi.mocked(requestFabricPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const { result } = renderHook(() => useFabricPreview(dto(16)))
    act(() => { void result.current.update(); void result.current.update() })
    await act(async () => { current.resolve(preview(16)); await current.promise })
    expect(result.current.result?.preview_id).toBe('preview-16')
    await act(async () => { old.reject(new Error('old request failed')); await old.promise.catch(() => undefined) })
    expect(result.current.status).toBe('ready')
    expect(result.current.error).toBeNull()
  })
})
