import { apiBaseUrl } from './client'
import type { PatternDocumentDTO } from '../model/types'

export type PatternFamily = 'grid' | 'radial' | 'along_curve' | 'free'

export interface PatternCandidate {
  id: PatternFamily
  confidence: number
  available: boolean
  parameters: Record<string, unknown>
  reason: string
}

export interface PatternAnalysis {
  document_id: string
  document_revision: number
  recommended: PatternFamily
  families: PatternCandidate[]
  warnings: string[]
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  })
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = data && typeof data === 'object' && 'message' in data
      ? String(data.message) : `HTTP ${response.status}`
    throw new Error(message)
  }
  return data as T
}

export async function analyzePattern(dto: PatternDocumentDTO, signal?: AbortSignal): Promise<PatternAnalysis> {
  const result = await post<PatternAnalysis>('/api/v1/analyze-pattern', { document: dto }, signal)
  if (result.document_id !== dto.document_id || result.document_revision !== dto.document_revision
      || !Array.isArray(result.families) || !Array.isArray(result.warnings)) {
    throw new Error('图案分析结果与当前项目不匹配。')
  }
  return result
}

export async function applyPattern(dto: PatternDocumentDTO, family: PatternFamily): Promise<PatternDocumentDTO> {
  const result = await post<PatternDocumentDTO>('/api/v1/apply-pattern', {
    document: dto, document_revision: dto.document_revision, family,
  })
  if (result.document_id !== dto.document_id || result.document_revision !== dto.document_revision + 1
      || !result.document || !Array.isArray(result.document.elements)) {
    throw new Error('图案结构转换结果与当前项目不匹配。')
  }
  return result
}
