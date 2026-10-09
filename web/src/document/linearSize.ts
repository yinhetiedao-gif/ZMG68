import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'
import { addField, addModifier, bindScalarModifierField, fieldReferencedOutside } from './editor'
import { asRecord } from './selectors'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterGroup } from './parameterSchema'

const OWNER = 'web_linear_size_effect'
export const linearSizeDefaults = { angle: 0, min_output: .6, max_output: 1.2, strength: 1 }
export type LinearSizeValues = typeof linearSizeDefaults
export interface LinearSizeDraft {
  kind: 'linear'; sourceKey: string; source: PatternDocumentDTO; bounds: BoundsMM; values: LinearSizeValues
}
export function linearSizeOwner(dto: PatternDocumentDTO) {
  const owner = asRecord(dto.document.metadata[OWNER])
  if (owner?.version !== 1) return null
  const field = dto.document.fields.find(item => item.id === owner.field_id && item.type === 'linear')
  const modifier = dto.document.modifiers.find(item => item.id === owner.modifier_id && item.type === 'size' && item.field_id === owner.field_id)
  return field && modifier ? { owner, field, modifier } : null
}
export function linearSizeGroup(catalog: ParameterCatalog | null): ParameterGroup | null {
  const angle = groupFor(catalog, 'field', 'linear')?.parameters.find(item => item.id === 'angle')
  const size = groupFor(catalog, 'modifier', 'size')
  if (!angle || !size) return null
  const labels = { min_output: '最小尺寸比例', max_output: '最大尺寸比例', strength: '作用强度' }
  const parameters = [ { ...angle, label: '渐变方向', default: linearSizeDefaults.angle },
    ...(['min_output', 'max_output', 'strength'] as const).map(id => {
      const definition = size.parameters.find(item => item.id === id)
      return definition ? { ...definition, label: labels[id], unit: '', default: linearSizeDefaults[id] } : null
    }) ]
  return parameters.some(item => !item) ? null : { label: '线性尺寸渐变', parameters: parameters as ParameterGroup['parameters'] }
}
export function openLinearSize(dto: PatternDocumentDTO, bounds: BoundsMM): LinearSizeDraft {
  const current = linearSizeOwner(dto)
  const mapping = asRecord(current?.modifier.mapping)
  const parameters = asRecord(current?.field.parameters)
  const storedBounds = asRecord(current?.owner.bounds_mm)
  const factor = (millimetresPerUnit(dto.document) ?? 1) / Number(current?.owner.mm_per_unit ?? millimetresPerUnit(dto.document) ?? 1)
  const box = storedBounds && Number.isFinite(factor) && factor > 0 &&
    ['min_x', 'min_y', 'max_x', 'max_y', 'width', 'height'].every(key => Number.isFinite(storedBounds[key]))
    ? { min_x: Number(storedBounds.min_x) * factor, min_y: Number(storedBounds.min_y) * factor,
      max_x: Number(storedBounds.max_x) * factor, max_y: Number(storedBounds.max_y) * factor,
      width: Number(storedBounds.width) * factor, height: Number(storedBounds.height) * factor, units: 'mm' as const } : bounds
  return { kind: 'linear', source: dto, sourceKey: JSON.stringify(dto), bounds: box,
    values: { angle: Number(parameters?.angle ?? linearSizeDefaults.angle),
      min_output: Number(mapping?.min_output ?? linearSizeDefaults.min_output),
      max_output: Number(mapping?.max_output ?? linearSizeDefaults.max_output),
      strength: Number(mapping?.strength ?? linearSizeDefaults.strength) } }
}

/** Configuration only; geometry is always produced by Python LinearField/SizeModifier.
 * The persisted projection limits use document world units, not viewport or mm. */
export function linearSizeCandidate(draft: LinearSizeDraft, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const group = linearSizeGroup(catalog)
  if (!group || group.parameters.some(item => !validateParameter(item, draft.values[item.id as keyof LinearSizeValues])))
    throw new Error('线性尺寸参数超出合法范围。')
  if (draft.values.min_output > draft.values.max_output) throw new Error('最小尺寸比例不能大于最大尺寸比例。')
  const dto = draft.source, scale = millimetresPerUnit(dto.document)
  if (!scale) throw new Error('当前文档缺少有效毫米映射。')
  const current = linearSizeOwner(dto)
  let working = dto, fieldId = current?.field.id as string | undefined
  if (!fieldId || fieldReferencedOutside(dto, fieldId, { metadataKeys: [OWNER], modifierId: current?.modifier.id as string })) {
    const created = addField(working, 'linear', catalog); working = created.dto; fieldId = created.id
  }
  // Advanced editing may rebind/remove the owned field. Still update our own
  // existing Size layer rather than stacking a second one over it.
  const recorded = asRecord(dto.document.metadata[OWNER])
  let modifierId = (current?.modifier.id ?? (recorded?.version === 1
    ? dto.document.modifiers.find(item => item.id === recorded.modifier_id && item.type === 'size')?.id : undefined)) as string | undefined
  if (!modifierId) {
    working = addModifier(working, 'size', catalog)
    modifierId = working.document.modifiers.at(-1)!.id as string
  }
  working = bindScalarModifierField(working, modifierId, fieldId)
  const box = draft.bounds, radians = draft.values.angle * Math.PI / 180
  const projections = [[box.min_x, box.min_y], [box.min_x, box.max_y],
    [box.max_x, box.min_y], [box.max_x, box.max_y]].map(([x, y]) => (x * Math.cos(radians) + y * Math.sin(radians)) / scale)
  const start = Math.min(...projections), end = Math.max(...projections)
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) throw new Error('图案没有有效渐变范围。')
  return { ...working, document_revision: dto.document_revision,
    document: { ...working.document,
      fields: working.document.fields.map(field => field.id === fieldId
        ? { ...field, enabled: true, parameters: { angle: draft.values.angle, start, end } } : field),
      modifiers: working.document.modifiers.map(modifier => modifier.id === modifierId
        ? { ...modifier, enabled: true, mapping: { ...asRecord(modifier.mapping),
          min_output: draft.values.min_output, max_output: draft.values.max_output, strength: draft.values.strength } } : modifier),
      metadata: { ...working.document.metadata, [OWNER]: { version: 1, field_id: fieldId, modifier_id: modifierId, bounds_mm: box, mm_per_unit: scale } },
    } }
}
