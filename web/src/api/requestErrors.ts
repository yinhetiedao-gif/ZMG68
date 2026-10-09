export class HttpRequestError extends Error {
  readonly code: string
  readonly failureId: string | null
  constructor(readonly status: number, payload: unknown) {
    const error = requestError(status, payload)
    super(error.message); this.code = error.code; this.failureId = error.failureId
  }
}

/** The HTTP boundary uses both ErrorDTO and fusion-report envelopes. */
export function requestError(status: number, payload: unknown) {
  const root = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, any> : {}
  const error = root.error && typeof root.error === 'object' ? root.error : root
  const detail = root.detail && typeof root.detail === 'object' && !Array.isArray(root.detail) ? root.detail : {}
  const validationMessages = Array.isArray(root.detail) ? root.detail
    .filter(item => item && typeof item.msg === 'string').map(item => item.msg).join('；') : ''
  const code = typeof error.code === 'string' ? error.code
    : typeof detail.code === 'string' ? detail.code : status === 404 ? 'route_not_found' : 'http_error'
  const reason = typeof error.message === 'string' ? error.message
    : status === 404 ? `当前后端没有此接口或结果，请检查运行中的项目服务。${typeof root.detail === 'string' ? ` 原始响应：${root.detail}` : ''}`
      : typeof root.detail === 'string' ? root.detail : typeof detail.message === 'string' ? detail.message
        : validationMessages ||
          '后端未返回可读取的错误说明。'
  const details = error.details ?? detail.details
  const failureId = root.fusion_report?.failure_id ?? details?.failure_id
  return { code, reason, failureId: typeof failureId === 'string' ? failureId : null,
    message: `${reason}${code === 'staging_busy' ? ' 请等待当前任务结束后再操作。' : ''}（HTTP ${status}）` }
}
