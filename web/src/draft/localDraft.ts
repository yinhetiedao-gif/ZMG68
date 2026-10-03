import type { PatternDocumentDTO } from '../model/types'

const DB_NAME = 'xiaomang-pattern-lab-drafts'
const STORE = 'drafts'
const KEY = 'last-working-draft'
const PRE_EXAMPLE_KEY = 'before-example-draft'
const MAX_REQUEST_BYTES = 2 * 1024 * 1024

export interface SourceAssetDraft {
  blob: Blob
  filename: string
  media_type: string
}

export interface LocalDraft {
  key: typeof KEY | typeof PRE_EXAMPLE_KEY
  schema_version: '1.0'
  saved_at: string
  dto: PatternDocumentDTO
  file_name: string | null
  source_asset: SourceAssetDraft | null
}

export class LocalDraftError extends Error {}

function database(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') return Promise.reject(new LocalDraftError('当前浏览器不支持本地草稿存储。'))
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, { keyPath: 'key' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new LocalDraftError('无法打开本地草稿存储。'))
    request.onblocked = () => reject(new LocalDraftError('本地草稿正被另一页面占用。'))
  })
}

function evaluateBytes(dto: PatternDocumentDTO): number {
  return new TextEncoder().encode(JSON.stringify({
    schema_version: '1.0', document_id: dto.document_id,
    document_revision: dto.document_revision, document: dto,
  })).byteLength
}

export function validateDraftDocument(dto: unknown): asserts dto is PatternDocumentDTO {
  if (!dto || typeof dto !== 'object') throw new LocalDraftError('本地草稿内容无效。')
  const value = dto as Partial<PatternDocumentDTO>
  const doc = value.document
  if (value.schema_version !== '1.0' || typeof value.document_id !== 'string' || !value.document_id
      || !Number.isSafeInteger(value.document_revision) || (value.document_revision ?? -1) < 0
      || !doc || doc.schema_version !== 1 || !doc.canvas
      || !Number.isFinite(doc.canvas.width) || !Number.isFinite(doc.canvas.height)
      || doc.canvas.width <= 0 || doc.canvas.height <= 0
      || !Array.isArray(doc.elements) || !Array.isArray(doc.fields) || !Array.isArray(doc.modifiers)
      || !doc.metadata || !Array.isArray(value.assets) || value.assets.length !== 0) {
    throw new LocalDraftError('本地草稿与当前项目协议不兼容。')
  }
  const ids = new Set<string>()
  for (const item of doc.elements) {
    if (!item || typeof item.id !== 'string' || !item.id || ids.has(item.id)
        || !Number.isFinite(item.x) || !Number.isFinite(item.y)
        || !Number.isFinite(item.width) || !Number.isFinite(item.height)
        || item.width <= 0 || item.height <= 0) throw new LocalDraftError('本地草稿元素无效。')
    ids.add(item.id)
  }
  if (evaluateBytes(value as PatternDocumentDTO) > MAX_REQUEST_BYTES) {
    throw new LocalDraftError('当前设计超过服务端 2 MiB 请求限制，未写入本地草稿；请减少项目大小。')
  }
}

export async function saveDraft(dto: PatternDocumentDTO, fileName: string | null,
  sourceAsset: SourceAssetDraft | null): Promise<LocalDraft> {
  return writeDraft(KEY, dto, fileName, sourceAsset)
}

/** One recoverable pre-example work slot; it uses the same canonical DTO, not a template format. */
export async function saveBeforeExampleDraft(dto: PatternDocumentDTO, fileName: string | null,
  sourceAsset: SourceAssetDraft | null): Promise<LocalDraft> {
  return writeDraft(PRE_EXAMPLE_KEY, dto, fileName, sourceAsset)
}

async function writeDraft(key: LocalDraft['key'], dto: PatternDocumentDTO, fileName: string | null,
  sourceAsset: SourceAssetDraft | null): Promise<LocalDraft> {
  validateDraftDocument(dto)
  const draft: LocalDraft = {
    key, schema_version: '1.0', saved_at: new Date().toISOString(),
    dto, file_name: fileName, source_asset: sourceAsset,
  }
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put(draft)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(new LocalDraftError('本地草稿保存失败；当前设计仍在此页面中。'))
      tx.onabort = () => reject(new LocalDraftError('本地草稿保存失败；浏览器存储空间可能不足。'))
    })
    return draft
  } finally { db.close() }
}

export async function loadDraft(): Promise<LocalDraft | null> {
  return readDraft(KEY)
}

export async function loadBeforeExampleDraft(): Promise<LocalDraft | null> {
  return readDraft(PRE_EXAMPLE_KEY)
}

async function readDraft(key: LocalDraft['key']): Promise<LocalDraft | null> {
  const db = await database()
  try {
    const draft = await new Promise<LocalDraft | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const request = tx.objectStore(STORE).get(key)
      request.onsuccess = () => resolve(request.result as LocalDraft | undefined)
      request.onerror = () => reject(new LocalDraftError('无法读取本地草稿。'))
    })
    if (!draft) return null
    if (draft.schema_version !== '1.0') throw new LocalDraftError('本地草稿版本不受支持。')
    validateDraftDocument(draft.dto)
    return draft
  } finally { db.close() }
}

export async function clearDraft(): Promise<void> {
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).delete(KEY)
      tx.objectStore(STORE).delete(PRE_EXAMPLE_KEY)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(new LocalDraftError('无法清除本地草稿。'))
    })
  } finally { db.close() }
}
