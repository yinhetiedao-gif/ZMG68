import { describe, it, expect, vi } from 'vitest'
import { coordinateComputeRequests } from './computeRequests'
import { requestError } from '../api/requestErrors'
import { requestFabricFusion } from '../api/fabricFusion'
import { phase1aDocument } from '../test/phase1aFixture'

describe('Phase 1A task coordination', () => {
  it('guards same-frame/cross-entry calls, lets lightweight/download calls pass, drains cancelled CPU requests', async () => {
    let done!: (response: Response) => void
    const fetcher = vi.fn<typeof fetch>((url) => String(url).endsWith('/fusion')
      ? new Promise(resolve => { done = resolve }) : Promise.resolve(new Response('{}')))
    const states: boolean[] = []
    const tasks = coordinateComputeRequests(fetcher, state => states.push(state))
    const abort = new AbortController()
    const first = tasks.fetcher('/api/v1/fabric/fusion', { method: 'POST', signal: abort.signal })
    const cancelled = expect(first).rejects.toThrow()
    expect(tasks.isBusy()).toBe(true)
    for (const path of ['fabric/fusion', 'fabric/candidate', 'fabric/preview', 'manufacturing/build']) {
      const response = await tasks.fetcher(`/api/v1/${path}`, { method: 'POST' })
      expect(response.status).toBe(429)
    }
    expect(fetcher).toHaveBeenCalledTimes(1)
    await tasks.fetcher('/api/v1/health')
    await tasks.fetcher('/api/v1/fabric/result/model.stl', { method: 'POST' })
    abort.abort()
    expect(fetcher.mock.calls[0][1]?.signal).toBeUndefined()
    expect(tasks.isBusy()).toBe(true)
    done(new Response('{}'))
    await cancelled
    expect(tasks.isBusy()).toBe(false)
    expect(states).toEqual([true, false])
    await tasks.fetcher('/api/v1/fabric/candidate', { method: 'POST' })
    expect(tasks.isBusy()).toBe(false)
  })
  it('releases after HTTP errors and network failures without retrying', async () => {
    const failed = vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValue(new Response('{}', { status: 500 }))
    const tasks = coordinateComputeRequests(failed, () => {})
    await expect(tasks.fetcher('/api/v1/fabric/fusion', { method: 'POST' })).rejects.toThrow('network')
    expect(tasks.isBusy()).toBe(false)
    expect((await tasks.fetcher('/api/v1/fabric/fusion', { method: 'POST' })).status).toBe(500)
    expect(tasks.isBusy()).toBe(false)
    expect(failed).toHaveBeenCalledTimes(2)
  })
  it('an old cancelled waiter cannot clear the busy state of the next task', async () => {
    const finish: ((response: Response) => void)[] = []
    const tasks = coordinateComputeRequests(async () => new Promise<Response>(resolve => finish.push(resolve)), () => {})
    const abort = new AbortController()
    const old = tasks.fetcher('/api/v1/fabric/candidate', { method: 'POST', signal: abort.signal }).catch(() => undefined)
    abort.abort(); finish[0](new Response('{}'))
    await old
    const next = tasks.fetcher('/api/v1/fabric/fusion', { method: 'POST' })
    await old
    expect(tasks.isBusy()).toBe(true)
    finish[1](new Response('{}'))
    await next
    expect(tasks.isBusy()).toBe(false)
  })
  it('reads root/nested/detail formats and retains the actual staging busy business code', async () => {
    for (const payload of [{ code: 'staging_busy', message: '服务器正在计算', details: {} },
      { error: { code: 'staging_busy', message: '服务器正在计算', details: {} } },
      { detail: { code: 'staging_busy', message: '服务器正在计算' } }]) {
      expect(requestError(429, payload)).toMatchObject({ code: 'staging_busy', failureId: null })
      const failure = await requestFabricFusion(phase1aDocument(), undefined,
        async () => new Response(JSON.stringify(payload), { status: 429 })).catch(error => error)
      expect(failure.message).toContain('等待')
      expect(failure.diagnostics.error_code).toBe('staging_busy')
      expect(failure.diagnostics.stage).toBe('request')
    }
    expect(requestError(502, null)).toMatchObject({ code: 'http_error', failureId: null })
    expect(requestError(422, { detail: 'bad input' }).message).toContain('bad input')
    expect(requestError(422, { detail: [{ msg: 'height must be positive' }] }).message).toContain('height must be positive')
  })
})
