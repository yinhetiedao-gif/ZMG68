export const EXPECTED_SCHEMA_VERSION = '1.0' as const
export const EXPECTED_UNITS = 'mm' as const

export interface HealthResponse {
  status: string
  contract_version: string
}

export interface ContractResponse {
  schema_version: string
  units: string
}

export interface BackendHandshake {
  health: HealthResponse
  contract: ContractResponse
}

export class BackendOfflineError extends Error {
  readonly kind = 'offline'
}

export class ContractMismatchError extends Error {
  readonly kind = 'incompatible'
}

type FetchLike = typeof fetch

export function apiBaseUrl(): string {
  // The local development URL is supplied by .env.development; production
  // deployments must explicitly set VITE_API_BASE_URL at build time.
  return (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
}

async function getJson<T>(path: string, fetcher: FetchLike, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetcher(`${apiBaseUrl()}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch {
    throw new BackendOfflineError('无法连接 Python 后端。请先启动本机 WM3 服务。')
  }
  if (!response.ok) {
    throw new BackendOfflineError(`Python 后端暂不可用（HTTP ${response.status}）。`)
  }
  try {
    return (await response.json()) as T
  } catch {
    throw new ContractMismatchError('后端返回了无法识别的 JSON。')
  }
}

export async function checkBackend(fetcher: FetchLike = fetch, signal?: AbortSignal): Promise<BackendHandshake> {
  const health = await getJson<HealthResponse>('/api/v1/health', fetcher, signal)
  if (health?.status !== 'ok' || health.contract_version !== EXPECTED_SCHEMA_VERSION) {
    throw new ContractMismatchError(`后端协议版本不匹配：需要 ${EXPECTED_SCHEMA_VERSION}。`)
  }
  const contract = await getJson<ContractResponse>('/api/v1/contract', fetcher, signal)
  if (contract?.schema_version !== EXPECTED_SCHEMA_VERSION || contract.units !== EXPECTED_UNITS) {
    throw new ContractMismatchError(`协议或单位不匹配：需要 v${EXPECTED_SCHEMA_VERSION} / ${EXPECTED_UNITS}。`)
  }
  return { health, contract }
}
