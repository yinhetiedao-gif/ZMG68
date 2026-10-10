import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'

export function isOriginalShape(dto: PatternDocumentDTO | null): boolean {
  if (!dto) return false
  const config = dto.document.metadata.fabric_config as Record<string, unknown> | undefined
  // Absent Fabric config is the existing uniform original-outline pipeline.
  // A legacy config with null/missing unit_cell is NOT globally reinterpreted.
  return !config || config.shape_source === 'original'
}
export function originalShape(dto: PatternDocumentDTO | null) {
  return (dto?.document.metadata.fabric_config as { original_shape?: { size_scale: number; height_mm: number } } | undefined)?.original_shape ?? null
}
export function setOriginalShape(dto: PatternDocumentDTO, catalog: ParameterCatalog | null,
  edits: Record<string, ParameterValue> = {}): PatternDocumentDTO {
  const group = groupFor(catalog, 'fabric_original', 'original')
  const base = groupFor(catalog, 'fabric_base', 'solid')
  if (!group || !base) throw new Error('后端尚未提供原图形状参数，请重试加载参数。')
  const config = dto.document.metadata.fabric_config as Record<string, any> | undefined
  const values = { ...Object.fromEntries(group.parameters.map(p => [p.id, p.default])), ...config?.original_shape, ...edits }
  for (const p of group.parameters) if (!validateParameter(p, values[p.id])) throw new Error(`原图形状参数 ${p.label} 无效。`)
  return { ...dto, document_revision: dto.document_revision + 1, document: { ...dto.document, metadata: {
    ...dto.document.metadata, fabric_config: { ...config, config_version: 1, shape_source: 'original',
      output_mode: config?.output_mode ?? (config ? 'cells_with_base' : 'cells_only'),
      base: config?.base ?? { type: 'solid', ...Object.fromEntries(base.parameters.map(p => [p.id, p.default])) },
      original_shape: values,
    },
  } } }
}
/** Preview-only candidate for the legacy uniform pipeline. Never saved or committed. */
export function originalPreviewDocument(dto: PatternDocumentDTO | null, catalog: ParameterCatalog | null, height: number) {
  if (!dto || !isOriginalShape(dto) || originalShape(dto)) return dto
  if (!groupFor(catalog, 'fabric_original', 'original') || !Number.isFinite(height) || height <= 0) return null
  return { ...setOriginalShape(dto, catalog, { height_mm: height }), document_revision: dto.document_revision }
}
