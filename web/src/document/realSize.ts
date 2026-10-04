import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit, withMillimetreMapping } from '../model/project'

interface SizeConfirmation { width_mm: number; height_mm: number; mm_per_unit: number }

function confirmation(dto: PatternDocumentDTO): SizeConfirmation | null {
  const value = dto.document.metadata.web_real_size_confirmation
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const item = value as Partial<SizeConfirmation>
  return typeof item.width_mm === 'number' && typeof item.height_mm === 'number' &&
    typeof item.mm_per_unit === 'number' ? item as SizeConfirmation : null
}

export function realSizeConfirmed(dto: PatternDocumentDTO, bounds: BoundsMM | null): boolean {
  const marker = confirmation(dto)
  const scale = millimetresPerUnit(dto.document)
  return Boolean(marker && bounds && scale &&
    Math.abs(marker.width_mm - bounds.width) < 0.001 &&
    Math.abs(marker.height_mm - bounds.height) < 0.001 &&
    Math.abs(marker.mm_per_unit - scale) < 1e-9)
}

/** Reuse the document's single world-mm mapping; never rescale the mesh directly. */
export function confirmUniformRealSize(dto: PatternDocumentDTO, bounds: BoundsMM,
  widthMm: number, heightMm: number): PatternDocumentDTO {
  const scale = millimetresPerUnit(dto.document)
  if (!scale || ![widthMm, heightMm, bounds.width, bounds.height].every((value) =>
    Number.isFinite(value) && value > 0)) throw new Error('真实尺寸必须是有限的正数。')
  const ratioX = widthMm / bounds.width
  const ratioY = heightMm / bounds.height
  if (Math.abs(ratioX - ratioY) > 1e-8 * Math.max(ratioX, ratioY))
    throw new Error('当前毫米映射只支持等比尺寸；请锁定比例。')
  const mapped = withMillimetreMapping(dto, scale * ratioX)
  return {
    ...mapped, document_revision: dto.document_revision + 1,
    document: { ...mapped.document, metadata: { ...mapped.document.metadata,
      web_import_scale_unconfirmed: false,
      web_real_size_confirmation: { width_mm: widthMm, height_mm: heightMm, mm_per_unit: scale * ratioX },
    } },
  }
}
