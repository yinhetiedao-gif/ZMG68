// Configuration adapter only. Python SharedFieldEngine owns both evaluations.
import type { PatternDocumentDTO } from '../model/types'
import { asRecord, STACK_KEY } from './selectors'
import { addModifier } from './editor'
import { linearSizeOwner, type LinearSizeDraft } from './linearSize'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterGroup } from './parameterSchema'

export const isDualPreset = (id?: string | null) => id === 'digital-weave' || id === 'vortex-scales'
export function dualOwner(dto: PatternDocumentDTO) {
  const saved = asRecord(dto.document.metadata.web_linear_size_effect)
  const record = asRecord(asRecord(dto.document.metadata.web_pattern_preset)?.dual_binding) ??
    (saved?.rotation_modifier_id ? { size_modifier_id: saved.modifier_id, rotation_modifier_id: saved.rotation_modifier_id } : null)
  if (!record) return null
  const size = dto.document.modifiers.find(m => m.id === record.size_modifier_id && m.type === 'size')
  const rotation = dto.document.modifiers.find(m => m.id === record.rotation_modifier_id && m.type === 'rotation')
  return size && rotation ? { record, size, rotation } : null
}
export function assertDualSafe(dto: PatternDocumentDTO) {
  const stack = asRecord(dto.document.metadata[STACK_KEY])
  const layers = Array.isArray(stack?.modifiers) ? stack.modifiers.map(asRecord) : []
  const legacy = asRecord(stack?.rotation_field)
  if (stack?.enabled !== false && !layers.length && legacy &&
      (String(legacy.mode ?? 'constant') !== 'constant' || Number(legacy.angle ?? 0) !== 0))
    throw new Error('当前旧隐式旋转堆栈有生效效果，不能安全应用双绑定预设；原作品保持不变，不自动迁移。')
  if (stack?.enabled !== false && layers.some(l => l?.enabled !== false && l?.type === 'position') ||
      dto.document.modifiers.some(m => m.type === 'field_position' && m.enabled !== false))
    throw new Error('当前存在后置位置或位置场效果，双绑定的空间采样语义不安全；请明确停用后再试，原作品保持不变。')
}
export function dualRotationGroup(catalog: ParameterCatalog | null): ParameterGroup {
  const group = groupFor(catalog, 'modifier', 'rotation')
  if (!group) throw new Error('缺少现有旋转映射参数。')
  return { label: '预设旋转（全图）', parameters: [
    ...group.parameters.filter(p => ['min_output', 'max_output', 'strength'].includes(p.id))
      .map(p => ({ ...p, id: `preset_rotation_${p.id}`, label: p.id === 'min_output' ? '起始旋转角' : p.id === 'max_output' ? '终点旋转角' : '旋转强度' })),
    { id: 'preset_rotation_remap_curve', label: '旋转映射', type: 'select', value: 'linear', default: 'linear', unit: '',
      min: null, max: null, step: null, options: [{ value: 'linear', label: '线性（不对称轮廓可能接缝）' }, { value: 'bell', label: '钟形（相位两端回到同一角度）' }] },
  ] }
}
export function applyDualBinding(result: PatternDocumentDTO, draft: LinearSizeDraft, catalog: ParameterCatalog | null) {
  assertDualSafe(draft.source)
  const owned = linearSizeOwner(result)
  if (!owned || !draft.presetRotation) throw new Error('缺少双绑定尺寸层或旋转配置。')
  for (const p of dualRotationGroup(catalog).parameters)
    if (!validateParameter(p, draft.presetRotation[p.id.slice(16) as keyof typeof draft.presetRotation]))
      throw new Error('旋转映射参数无效。')
  const previous = dualOwner(draft.source)
  let working = result, rotationId = previous?.rotation.id
  if (!rotationId) { working = addModifier(working, 'rotation', catalog); rotationId = working.document.modifiers.at(-1)!.id }
  const mapping = { ...draft.presetRotation, invert: false, falloff: 1, clamp: true }
  return { ...working, document_revision: result.document_revision, document: { ...working.document,
    modifiers: working.document.modifiers.map(m => m.id === rotationId
      ? { ...m, enabled: true, field_id: owned.field.id, mapping, region: undefined, influence_areas: undefined }
      : m.id === owned.modifier.id ? { ...m, mapping: { ...asRecord(m.mapping), remap_curve: draft.presetId === 'vortex-scales' ? 'bell' : 'linear', falloff: 1 } } : m),
    metadata: { ...working.document.metadata,
      web_linear_size_effect: { ...asRecord(working.document.metadata.web_linear_size_effect), rotation_modifier_id: rotationId },
      web_pattern_preset: {
      ...asRecord(working.document.metadata.web_pattern_preset), dual_binding: {
        field_id: owned.field.id, size_modifier_id: owned.modifier.id, rotation_modifier_id: rotationId,
      }, anchor_native: draft.presetAnchorNative,
    } },
  } }
}
