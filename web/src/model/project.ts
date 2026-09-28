import type { PatternDocument, PatternDocumentDTO, SourceElement } from './types'

const types = new Set(['circle', 'ellipse', 'rect', 'path', 'filled_region'])
const absolutePath = /(?:^[A-Za-z]:[\\/]|^\\\\|^\/(?:Users|home|tmp|var|mnt)\/|file:\/\/)/i

export class ProjectOpenError extends Error {}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function finitePositive(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function clearAssetPath(holder: Record<string, unknown>, key: string, warnings: string[]): void {
  if (typeof holder[key] === 'string' && holder[key] && absolutePath.test(holder[key])) {
    holder[key] = ''
    warnings.push('本机图片/矢量路径未传输；图片驱动效果需要后续资产接口才能重现。')
  }
}

function rejectOtherLocalPaths(value: unknown): void {
  if (typeof value === 'string' && absolutePath.test(value)) {
    throw new ProjectOpenError('项目含尚未支持的本机资源路径，已阻止向后端发送。')
  }
  if (Array.isArray(value)) value.forEach(rejectOtherLocalPaths)
  else if (record(value)) Object.values(value).forEach(rejectOtherLocalPaths)
}

/**
 * Read the official PatternDocument JSON. Only the WM2 transport wrapper and
 * its explicit asset-path redaction are added; this is not another project format.
 */
export function prepareProject(text: string, documentId: string): {
  dto: PatternDocumentDTO
  warnings: string[]
  needsMillimetreMapping: boolean
} {
  let parsed: unknown
  try {
    parsed = JSON.parse(text) as unknown
  } catch {
    throw new ProjectOpenError('项目不是有效的 JSON 文件。')
  }
  if (!record(parsed) || !record(parsed.canvas) || !Array.isArray(parsed.elements)) {
    throw new ProjectOpenError('这不是 PatternDocument 项目文件。')
  }
  if (parsed.schema_version !== undefined && parsed.schema_version !== 1) {
    throw new ProjectOpenError('不支持的项目版本。')
  }
  if (!finitePositive(parsed.canvas.width) || !finitePositive(parsed.canvas.height)) {
    throw new ProjectOpenError('项目画布宽高无效。')
  }
  const ids = new Set<string>()
  for (const item of parsed.elements) {
    if (!record(item) || typeof item.id !== 'string' || !item.id || ids.has(item.id)
        || !types.has(String(item.type))
        || !Number.isFinite(item.x) || !Number.isFinite(item.y)
        || !finitePositive(item.width) || !finitePositive(item.height)) {
      throw new ProjectOpenError('项目包含无效或重复的 Element。')
    }
    ids.add(item.id)
  }
  const document = structuredClone(parsed) as unknown as PatternDocument
  document.schema_version = 1
  document.reference ??= { source_path: '', visible: false }
  document.groups ??= []
  document.transforms ??= {}
  document.metadata ??= {}
  document.fields ??= []
  document.modifiers ??= []
  const warnings: string[] = []
  clearAssetPath(document.reference, 'source_path', warnings)
  for (const key of ['metadata', 'preprocessing']) {
    const section = document.reference[key]
    if (record(section)) {
      for (const name of Object.keys(section)) {
        if (name.endsWith('path')) clearAssetPath(section, name, warnings)
      }
    }
  }
  clearAssetPath(document.metadata, 'source_svg', warnings)
  for (const field of document.fields) {
    if (field.type === 'image' && record(field.parameters)) {
      clearAssetPath(field.parameters, 'image_path', warnings)
    }
  }
  rejectOtherLocalPaths(document)
  const scale = millimetresPerUnit(document)
  return {
    dto: {
      schema_version: '1.0',
      document_id: documentId,
      document_revision: 0,
      document,
      assets: [],
    },
    warnings: [...new Set(warnings)],
    needsMillimetreMapping: scale === null,
  }
}

export function millimetresPerUnit(document: PatternDocument): number | null {
  if (finitePositive(document.canvas.mm_per_unit)) return document.canvas.mm_per_unit
  return document.canvas.unit === 'mm' ? 1 : null
}

export function withMillimetreMapping(dto: PatternDocumentDTO, mmPerUnit: number): PatternDocumentDTO {
  if (!finitePositive(mmPerUnit)) throw new ProjectOpenError('毫米映射必须是大于零的有限数。')
  return {
    ...dto,
    document: { ...dto.document, canvas: { ...dto.document.canvas, mm_per_unit: mmPerUnit } },
  }
}

/** Only exact, free source elements can be edited by WM5. Generated Grid IDs are not proof of source mapping. */
export function directSourceElement(dto: PatternDocumentDTO, finalId: string, finalX: number, finalY: number): SourceElement | null {
  const document = dto.document
  if (document.metadata['xiaomang_pattern_lab.parametric'] || document.fields.length || document.modifiers.length) return null
  const source = document.elements.find((item) => item.id === finalId)
  const scale = millimetresPerUnit(document)
  if (!source || !scale || !source.visible) return null
  if (Math.abs(source.x * scale - finalX) > 1e-5 || Math.abs(source.y * scale - finalY) > 1e-5) return null
  return source
}

export function moveSourceElement(dto: PatternDocumentDTO, elementId: string, dxMm: number, dyMm: number): PatternDocumentDTO {
  const scale = millimetresPerUnit(dto.document)
  if (!scale || !Number.isFinite(dxMm) || !Number.isFinite(dyMm)) throw new ProjectOpenError('无法将拖动转换为项目毫米坐标。')
  const source = dto.document.elements.find((item) => item.id === elementId)
  if (!source) throw new ProjectOpenError('找不到可编辑的源元素。')
  const next = { ...source, x: source.x + dxMm / scale, y: source.y + dyMm / scale }
  const transforms = { ...dto.document.transforms }
  if (transforms[elementId]) transforms[elementId] = { ...transforms[elementId], x: next.x, y: next.y }
  return {
    ...dto,
    document_revision: dto.document_revision + 1,
    document: {
      ...dto.document,
      elements: dto.document.elements.map((item) => item.id === elementId ? next : item),
      transforms,
    },
  }
}
