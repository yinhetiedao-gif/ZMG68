import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'
import { asRecord, STACK_KEY } from './selectors'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterGroup } from './parameterSchema'
const OWNER = 'web_radial_size_effect'
export interface RadialSizeValues { center_x: number; center_y: number; radius: number; min_scale: number; max_scale: number; strength: number }
export interface RadialSizeDraft { kind: 'radial'; sourceKey: string; source: PatternDocumentDTO; bounds: BoundsMM; values: RadialSizeValues }
export function radialSizeDefaults(bounds: BoundsMM): RadialSizeValues {
  return { center_x: (bounds.min_x + bounds.max_x) / 2, center_y: (bounds.min_y + bounds.max_y) / 2,
    radius: Math.hypot(bounds.width, bounds.height) / 2, min_scale: 1.2, max_scale: .6, strength: 1 }
}
export function radialSizeLayer(dto: PatternDocumentDTO) {
  const owner = asRecord(dto.document.metadata[OWNER]), stack = asRecord(dto.document.metadata[STACK_KEY])
  return owner?.version === 1 && Array.isArray(stack?.modifiers)
    ? stack.modifiers.map(asRecord).find(item => item && item.id === owner.layer_id && item.type === 'size' && asRecord(item.parameters)?.mode === 'radial') ?? null : null
}
export function radialSizeGroup(catalog: ParameterCatalog | null, dto: PatternDocumentDTO, bounds?: BoundsMM): ParameterGroup | null {
  const coords = groupFor(catalog, 'field', 'ring'), mapping = groupFor(catalog, 'modifier', 'size')
  const scale = millimetresPerUnit(dto.document)
  if (!coords || !mapping || !scale) return null
  const canvas = dto.document.canvas
  const defaults = radialSizeDefaults(bounds ?? { min_x: (canvas.origin_x ?? 0) * scale, min_y: (canvas.origin_y ?? 0) * scale,
    max_x: ((canvas.origin_x ?? 0) + canvas.width) * scale, max_y: ((canvas.origin_y ?? 0) + canvas.height) * scale,
    width: canvas.width * scale, height: canvas.height * scale, units: 'mm' })
  const parameters = ['center_x', 'center_y', 'radius'].map(id => {
    const p = coords.parameters.find(item => item.id === id)
    return p ? { ...p, default: defaults[id as keyof RadialSizeValues], label: id === 'radius' ? '影响半径' : id === 'center_x' ? '中心 X' : '中心 Y',
      min: id === 'radius' ? .01 * scale : p.min === null ? null : p.min * scale,
      max: p.max === null ? null : p.max * scale, unit: 'mm' } : null
  })
  for (const [id, sourceId, label] of [['min_scale', 'min_output', '中心尺寸比例'], ['max_scale', 'max_output', '外围尺寸比例'], ['strength', 'strength', '作用强度']]) {
    const p = mapping.parameters.find(item => item.id === sourceId)
    parameters.push(p ? { ...p, id, label, default: defaults[id as keyof RadialSizeValues], min: id === 'strength' ? p.min : .01, unit: '' } : null)
  }
  return parameters.some(item => !item) ? null : { label: '径向尺寸渐变', parameters: parameters as ParameterGroup['parameters'] }
}
export function openRadialSize(dto: PatternDocumentDTO, bounds: BoundsMM): RadialSizeDraft {
  const layer = radialSizeLayer(dto), p = asRecord(layer?.parameters), scale = millimetresPerUnit(dto.document) ?? 1
  return { kind: 'radial', source: dto, sourceKey: JSON.stringify(dto), bounds,
    values: p ? { center_x: Number(p.center_x) * scale, center_y: Number(p.center_y) * scale,
      radius: Number(p.radius) * scale, min_scale: Number(p.min_scale), max_scale: Number(p.max_scale), strength: Number(p.strength) }
      : radialSizeDefaults(bounds) }
}
/** Uses the existing ordered SizeFieldModifier(radial), not Ring or a new Field.
 * Never convert a non-neutral legacy stack into explicit layers implicitly. */
export function radialSizeCandidate(draft: RadialSizeDraft, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const dto = draft.source, group = radialSizeGroup(catalog, dto, draft.bounds), scale = millimetresPerUnit(dto.document)
  if (!group || !scale || group.parameters.some(p => !validateParameter(p, draft.values[p.id as keyof RadialSizeValues])))
    throw new Error('径向尺寸参数超出合法范围。')
  const stack = asRecord(dto.document.metadata[STACK_KEY]), layers = Array.isArray(stack?.modifiers) ? stack.modifiers : []
  if (stack?.enabled === false) throw new Error('当前有序效果堆栈已停用，请先明确启用；不会自动改变其他效果。')
  const legacySize = asRecord(stack?.size_field), legacyRotation = asRecord(stack?.rotation_field)
  if (stack && !layers.length && ((legacySize && Object.entries(legacySize).some(([key, value]) =>
    ['min_scale', 'max_scale', 'strength'].includes(key) && value !== 1 || key === 'mode' && value !== 'constant')) ||
    (legacyRotation && (String(legacyRotation.mode ?? 'constant') !== 'constant' || Number(legacyRotation.angle ?? 0) !== 0))))
    throw new Error('当前旧兼容堆栈有生效效果，无法安全追加径向层；原作品保持不变。')
  const existing = radialSizeLayer(dto), used = new Set(layers.map(item => asRecord(item)?.id))
  let index = 1; while (used.has(`radial-size-${index}`)) index++
  const id = existing?.id ?? `radial-size-${index}`
  const layer = { ...existing, id, type: 'size', enabled: true,
    parameters: { mode: 'radial', ...draft.values, center_x: draft.values.center_x / scale,
      center_y: draft.values.center_y / scale, radius: draft.values.radius / scale },
    scope: { mode: 'all', invert: false, selected_element_ids: [], center_x: 0, center_y: 0, radius: 50, width: 100, height: 100 } }
  return { ...dto, document: { ...dto.document, metadata: { ...dto.document.metadata,
    [OWNER]: { version: 1, layer_id: id }, [STACK_KEY]: { version: 1, enabled: true, source_kind: 'imported_elements',
      source_elements: structuredClone(dto.document.elements), ...stack,
      modifiers: existing ? layers.map(item => asRecord(item)?.id === id ? layer : item) : [...layers, layer] },
  } } }
}
