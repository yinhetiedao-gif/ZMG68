const endpoints = new Set(['/api/v1/manufacturing/build', '/api/v1/fabric/preview',
  '/api/v1/fabric/candidate', '/api/v1/fabric/fusion'])

/** One coordinator owned by App, not by a mode/panel that can unmount.
 * A cancelled UI waiter still drains the real HTTP request: abort is not proof
 * that the server has finished CPU work. Downloads/health/evaluate stay independent. */
export function coordinateComputeRequests(fetcher: typeof fetch, onBusy: (busy: boolean) => void) {
  let active: symbol | null = null
  const isBusy = () => active !== null
  const coordinated: typeof fetch = async (input, init) => {
    const path = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url,
      'http://local.invalid').pathname
    if (!endpoints.has(path) || (init?.method ?? 'GET').toUpperCase() !== 'POST') return fetcher(input, init)
    if (active) return new Response(JSON.stringify({ code: 'staging_busy',
      message: '当前页面已有计算任务正在执行。', recoverable: true }),
    { status: 429, headers: { 'Content-Type': 'application/json' } })
    init?.signal?.throwIfAborted()
    const token = Symbol('compute-request')
    active = token
    onBusy(true)
    try {
      const response = await fetcher(input, { ...init, signal: undefined })
      init?.signal?.throwIfAborted()
      return response
    } finally {
      if (active === token) { active = null; onBusy(false) }
    }
  }
  return { fetcher: coordinated, isBusy }
}
