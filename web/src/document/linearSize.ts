import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'
import { addField, addModifier, bindScalarModifierField, fieldReferencedOutside } from './editor'
import { asRecord } from './selectors'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterGroup, type ParameterValue } from './parameterSchema'
import { designCandidate, areasToMm, areasToNative, newInfluence, designValues, gridValues, validateInfluenceAreas, type InfluenceArea } from './designControls'

const OWNER = 'web_linear_size_effect'
export const linearSizeDefaults = { angle: 0, min_output: .6, max_output: 1.2, strength: 1 }
export type LinearSizeValues = typeof linearSizeDefaults & { scope_mode?: 'global' | 'local' | 'areas'; invert?: boolean; center_x?: number; center_y?: number;
  length?: number; width?: number; feather?: number; scope_angle?: number }
export function linearRegionDefaults(bounds: BoundsMM) {
  return { center_x: (bounds.min_x + bounds.max_x) / 2, center_y: (bounds.min_y + bounds.max_y) / 2,
    length: Math.max(.01, bounds.width * .65), width: Math.max(.01, bounds.height * .65), feather: 0 }
}
export interface LinearSizeDraft {
  kind: 'linear'; sourceKey: string; source: PatternDocumentDTO; bounds: BoundsMM; values: LinearSizeValues
  fieldType?: string; fieldParameters?: Record<string, unknown>; existingFieldId?: string
  explicitLinear?: boolean
  imageAsset?: PatternDocumentDTO['assets'][number]
  controlsOnly?: boolean
  presetId?: string
  designValues?: Record<string, ParameterValue>
  gridValues?: Record<string, number>
  artboard?: { width: number; height: number }
  influenceAreas?: InfluenceArea[]
  selectedArea?: string
  presetRotation?: { min_output: number; max_output: number; strength: number; remap_curve: 'linear' | 'bell' }
  ownedFieldConsumers?: { modifierIds: string[]; metadataKeys: string[] }
  presetAnchorNative?: { x: number; y: number }
}
export function linearSizeOwner(dto: PatternDocumentDTO) {
  const owner = asRecord(dto.document.metadata[OWNER])
  if (owner?.version !== 1) return null
  const field = dto.document.fields.find(item => item.id === owner.field_id)
  const modifier = dto.document.modifiers.find(item => item.id === owner.modifier_id && item.type === 'size' && item.field_id === owner.field_id)
  return field && modifier ? { owner, field, modifier } : null
}
export function linearSizeGroup(catalog: ParameterCatalog | null, draft?: LinearSizeDraft): ParameterGroup | null {
  const angle = groupFor(catalog, 'field', 'linear')?.parameters.find(item => item.id === 'angle')
  const size = groupFor(catalog, 'modifier', 'size')
  if (!angle || !size) return null
  const labels = { min_output: '最小尺寸比例', max_output: '最大尺寸比例', strength: '作用强度' }
  const parameters = [ ...(draft?.explicitLinear || draft?.existingFieldId || draft?.fieldType && draft.fieldType !== 'linear' ? [] : [{ ...angle, label: '渐变方向', default: linearSizeDefaults.angle }]),
    ...(['min_output', 'max_output', 'strength'] as const).map(id => {
      const definition = size.parameters.find(item => item.id === id)
      return definition ? { ...definition, label: labels[id], unit: '', default: linearSizeDefaults[id] } : null
    }) ]
  if (parameters.some(item => !item)) return null
  const result = parameters as ParameterGroup['parameters']
  if (draft?.values.scope_mode === 'local') {
    const coords = groupFor(catalog, 'field', 'ring')
    const scale = millimetresPerUnit(draft.source.document) ?? 1
    const defaults = linearRegionDefaults(draft.bounds)
    if (draft.explicitLinear || draft.existingFieldId || draft.fieldType && draft.fieldType !== 'linear') result.push({ ...angle, id: 'scope_angle', label: '区域方向', default: 0 })
    for (const [id, label] of [['center_x', '中心 X'], ['center_y', '中心 Y'], ['length', '区域长度'], ['width', '影响宽度'], ['feather', '边缘过渡']]) {
      const p = coords?.parameters.find(item => item.id === (id.startsWith('center') ? id : 'radius'))
      if (!p) return null
      result.push({ ...p, id, label, unit: 'mm', default: defaults[id as keyof typeof defaults],
        min: id.startsWith('center') ? p.min === null ? null : p.min * scale : id === 'feather' ? 0 : .01 * scale,
        max: p.max === null ? null : p.max * scale, slider_min: id.startsWith('center') ? null : id === 'feather' ? 0 : .01 * scale,
        slider_max: id.startsWith('center') ? null : Math.max(.01 * scale, draft.bounds.width, draft.bounds.height), slider_step: .1 })
    }
  }
  return { label: '线性尺寸渐变', parameters: result }
}

/** The catalog is the editable scalar-field contract. Composite has a separate
 * graph editor and cannot be created by this shortcut. No raster/field math here. */
export function sizeFieldTypes(catalog: ParameterCatalog | null) {
  return Object.entries(catalog?.definitions.field ?? {}).filter(([id, group]) => id !== 'composite' && group.parameters.length > 0)
}
export function sizeFieldGroup(catalog: ParameterCatalog | null, draft: LinearSizeDraft): ParameterGroup | null {
  const type = draft.fieldType ?? 'linear', group = groupFor(catalog, 'field', type)
  if (!group) return null
  // Legacy linear shortcut keeps its fitted projection domain and existing angle
  // control; existing fields expose their real start/end without rewriting them.
  if (type === 'linear' && !draft.existingFieldId && !draft.explicitLinear) return { label: group.label, parameters: [] }
  const mm = millimetresPerUnit(draft.source.document) ?? 1
  return { ...group, parameters: group.parameters.map(p => {
    const factor = p.unit === 'mm' && type !== 'distance' ? mm : 1
    return { ...p, id: `field_${p.id}`, default: typeof p.default === 'number' ? p.default * factor : p.default,
      min: p.min === null ? null : p.min * factor, max: p.max === null ? null : p.max * factor,
      step: p.step === null ? null : p.step * factor,
      slider_min: p.slider_min == null ? p.slider_min : p.slider_min * factor,
      slider_max: p.slider_max == null ? p.slider_max : p.slider_max * factor,
      slider_step: p.slider_step == null ? p.slider_step : p.slider_step * factor }
  }) }
}
export function sizeFieldValues(draft: LinearSizeDraft, catalog: ParameterCatalog | null): Record<string, ParameterValue> {
  const group = groupFor(catalog, 'field', draft.fieldType ?? 'linear'), mm = millimetresPerUnit(draft.source.document) ?? 1
  return Object.fromEntries((group?.parameters ?? []).map(p => {
    const stored = draft.fieldParameters?.[p.id] ?? p.default
    const value = p.type === 'select' ? String(stored) : stored as ParameterValue
    return [`field_${p.id}`, typeof value === 'number' && p.unit === 'mm' && draft.fieldType !== 'distance' ? value * mm : value]
  }))
}
export function changeSizeFieldParameter(draft: LinearSizeDraft, catalog: ParameterCatalog | null, key: string, value: ParameterValue): LinearSizeDraft {
  const p = sizeFieldGroup(catalog, draft)?.parameters.find(p => p.id === key)
  if (!p || !validateParameter(p, value)) throw new Error('场参数超出 Python Schema 允许范围。')
  const id = key.slice(6), native = groupFor(catalog, 'field', draft.fieldType ?? 'linear')!.parameters.find(p => p.id === id)!
  const mm = millimetresPerUnit(draft.source.document) ?? 1
  const stored = draft.fieldType === 'spiral' && id === 'direction' ? Number(value)
    : native.unit === 'mm' && draft.fieldType !== 'distance' && typeof value === 'number' ? value / mm : value
  return { ...draft, fieldParameters: { ...draft.fieldParameters, [id]: stored },
    values: id === 'angle' && draft.fieldType === 'linear' ? { ...draft.values, angle: Number(value) } : draft.values }
}
export function selectSizeField(draft: LinearSizeDraft, type: string, catalog: ParameterCatalog | null, existingId?: string): LinearSizeDraft {
  if (!sizeFieldTypes(catalog).some(([id]) => id === type)) throw new Error('当前目录不支持此尺寸驱动场。')
  const owned = linearSizeOwner(draft.source), ids = asRecord(owned?.owner.field_ids)
  const field = draft.source.document.fields.find(f => f.id === (existingId ?? ids?.[type]) && f.type === type)
  if (existingId && (!field || field.enabled === false)) throw new Error('请选择已启用且有效的参数场。')
  const created = !field ? addField(draft.source, type, catalog) : null
  const parameters = { ...asRecord(field?.parameters ?? created!.dto.document.fields.at(-1)!.parameters) }
  const fieldId = String(field?.id ?? ''), asset = draft.source.assets.find(a => a.role === `field:${fieldId}`)
  const scopeAngle = (draft.fieldType ?? 'linear') === 'linear' && !draft.existingFieldId && !draft.explicitLinear
    ? draft.values.angle : draft.values.scope_angle ?? 0
  return { ...draft, fieldType: type, existingFieldId: existingId, fieldParameters: parameters, imageAsset: asset,
    explicitLinear: type === 'linear' && (Boolean(existingId) || asRecord(owned?.owner.field_domains)?.[fieldId] === 'explicit'),
    values: { ...draft.values, angle: type === 'linear' ? draft.values.scope_mode === 'local' ? scopeAngle : Number(parameters.angle ?? 0) : draft.values.angle,
      scope_angle: scopeAngle } }
}
export function openLinearSize(dto: PatternDocumentDTO, bounds: BoundsMM): LinearSizeDraft {
  const current = linearSizeOwner(dto)
  const mapping = asRecord(current?.modifier.mapping)
  const parameters = asRecord(current?.field.parameters)
  const region = asRecord(current?.modifier.region)
  const mm = millimetresPerUnit(dto.document) ?? 1
  const storedBounds = asRecord(current?.owner.bounds_mm)
  const factor = (millimetresPerUnit(dto.document) ?? 1) / Number(current?.owner.mm_per_unit ?? millimetresPerUnit(dto.document) ?? 1)
  const box = storedBounds && Number.isFinite(factor) && factor > 0 &&
    ['min_x', 'min_y', 'max_x', 'max_y', 'width', 'height'].every(key => Number.isFinite(storedBounds[key]))
    ? { min_x: Number(storedBounds.min_x) * factor, min_y: Number(storedBounds.min_y) * factor,
      max_x: Number(storedBounds.max_x) * factor, max_y: Number(storedBounds.max_y) * factor,
      width: Number(storedBounds.width) * factor, height: Number(storedBounds.height) * factor, units: 'mm' as const } : bounds
  return { kind: 'linear', source: dto, sourceKey: JSON.stringify(dto), bounds: box,
    influenceAreas: areasToMm(current?.modifier.influence_areas, mm),
    ...(current && current.field.type !== 'linear' ? { fieldType: String(current.field.type), fieldParameters: { ...parameters } } : {}),
    ...(current?.owner.domain_mode === 'explicit' ? { explicitLinear: true, fieldType: String(current.field.type), fieldParameters: { ...parameters } } : {}),
    ...(current?.owner.source_mode === 'existing' ? { existingFieldId: String(current.field.id), fieldType: String(current.field.type), fieldParameters: { ...parameters } } : {}),
    imageAsset: dto.assets.find(a => a.role === `field:${current?.field.id}`),
    values: { angle: Number(parameters?.angle ?? linearSizeDefaults.angle),
      min_output: Number(mapping?.min_output ?? linearSizeDefaults.min_output),
      max_output: Number(mapping?.max_output ?? linearSizeDefaults.max_output),
      strength: Number(mapping?.strength ?? linearSizeDefaults.strength), invert: Boolean(mapping?.invert), scope_mode: current?.modifier.influence_areas ? 'areas' : region ? 'local' : 'global',
      ...(current && (current.field.type !== 'linear' || current.owner.domain_mode === 'explicit' || current.owner.source_mode === 'existing')
        ? { scope_angle: Number(region?.angle ?? 0) } : {}),
      ...linearRegionDefaults(box), ...(region ? { center_x: Number(region.center_x) * mm, center_y: Number(region.center_y) * mm,
        length: Number(region.length) * mm, width: Number(region.width) * mm, feather: Number(region.feather ?? 0) * mm,
        ...(current?.field.type !== 'linear' || current?.owner.domain_mode === 'explicit' || current?.owner.source_mode === 'existing' ? { scope_angle: Number(region.angle) } : {}) } : {}) } }
}

/** Configuration only; existing Python scalar fields and SizeModifier produce
 * all geometry. Legacy fitted linear limits stay in document world units. */
export function linearSizeCandidate(draft: LinearSizeDraft, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const controlled = designCandidate(draft.source, catalog, draft.designValues, draft.gridValues, draft.artboard)
  if (draft.controlsOnly) return controlled
  const group = linearSizeGroup(catalog, draft), fieldType = draft.fieldType ?? 'linear'
  if (!group || group.parameters.some(item => { const value = draft.values[item.id as keyof LinearSizeValues]; return value === undefined || !validateParameter(item, value) }))
    throw new Error('尺寸映射或作用范围参数超出合法范围。')
  if (draft.values.min_output > draft.values.max_output) throw new Error('最小尺寸比例不能大于最大尺寸比例。')
  const dto = controlled, scale = millimetresPerUnit(dto.document)
  if (!scale) throw new Error('当前文档缺少有效毫米映射。')
  if (draft.values.scope_mode === 'areas') validateInfluenceAreas(draft.influenceAreas ?? [], scale, catalog)
  const fieldGroup = sizeFieldGroup(catalog, draft)
  if (!fieldGroup || fieldGroup.parameters.some(p => !validateParameter(p, sizeFieldValues(draft, catalog)[p.id])))
    throw new Error('场参数缺失或超出 Python Schema 允许范围。')
  if (['image', 'distance'].includes(fieldType) && (!draft.imageAsset ||
      !['image/png', 'image/jpeg'].includes(draft.imageAsset.media_type)))
    throw new Error('此尺寸效果需要有效的 PNG/JPG 源资产。请选择源图片或已绑定图片的参数场；参考底图不会自动作为输入。')
  const local = draft.values.scope_mode === 'local'
  const region = local ? { center_x: draft.values.center_x! / scale, center_y: draft.values.center_y! / scale,
    length: draft.values.length! / scale, width: draft.values.width! / scale,
    angle: fieldType === 'linear' && !draft.existingFieldId && !draft.explicitLinear ? draft.values.angle : draft.values.scope_angle ?? 0, feather: draft.values.feather! / scale } : null
  if (region && (region.length <= 0 || region.width <= 0 || region.feather < 0 || region.feather > Math.min(region.length, region.width) / 2))
    throw new Error('范围必须有正长度和宽度；边缘过渡不能超过半长或半宽。')
  const current = linearSizeOwner(dto)
  // Advanced editing may rebind/remove the owned field. Still update our own
  // existing Size layer rather than stacking a second one over it.
  const recorded = asRecord(dto.document.metadata[OWNER])
  const ids = { ...asRecord(recorded?.field_ids), ...(current && !current.owner.source_mode ? { [String(current.field.type)]: current.field.id } : {}) }
  const existing = dto.document.fields.find(f => f.id === draft.existingFieldId && f.type === fieldType)
  const parameters = { ...asRecord(existing?.parameters), ...draft.fieldParameters }
  const externalUnchanged = !!existing && existing.enabled !== false && JSON.stringify(parameters) === JSON.stringify(asRecord(existing.parameters)) &&
    (!['image', 'distance'].includes(fieldType) || draft.imageAsset?.asset_id === dto.assets.find(a => a.role === `field:${existing.id}`)?.asset_id)
  let working = dto, fieldId = externalUnchanged ? String(existing!.id)
    : String((current?.field.type === fieldType && current.owner.source_mode !== 'existing' ? current?.field.id : ids[fieldType]) ?? '')
  if (!fieldId || !dto.document.fields.some(f => f.id === fieldId && f.type === fieldType) || (!externalUnchanged &&
      fieldReferencedOutside(dto, fieldId, { metadataKeys: [OWNER, ...(draft.ownedFieldConsumers?.metadataKeys ?? [])],
        modifierId: current?.modifier.id as string, modifierIds: draft.ownedFieldConsumers?.modifierIds }))) {
    const created = addField(working, fieldType, catalog); working = created.dto; fieldId = created.id
  }
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
  const centerProjection = region ? region.center_x * Math.cos(radians) + region.center_y * Math.sin(radians) : 0
  const start = region ? centerProjection - region.length / 2 : Math.min(...projections)
  const end = region ? centerProjection + region.length / 2 : Math.max(...projections)
  if (fieldType === 'linear' && (!Number.isFinite(start) || !Number.isFinite(end) || start >= end)) throw new Error('图案没有有效渐变范围。')
  const nativeParameters = externalUnchanged ? existing!.parameters : fieldType === 'linear' && !draft.existingFieldId && !draft.explicitLinear
    ? { angle: draft.values.angle, start, end }
    : { ...asRecord(working.document.fields.find(f => f.id === fieldId)?.parameters), ...parameters }
  if (!externalUnchanged) ids[fieldType] = fieldId
  const domains = { ...asRecord(recorded?.field_domains), [fieldId]: draft.existingFieldId || draft.explicitLinear ? 'explicit' : 'fitted' }
  return { ...working, document_revision: dto.document_revision,
    assets: draft.imageAsset && ['image', 'distance'].includes(fieldType)
      ? [...working.assets.filter(a => a.role !== `field:${fieldId}`), { ...draft.imageAsset, role: `field:${fieldId}` }] : working.assets,
    document: { ...working.document,
      fields: working.document.fields.map(field => field.id === fieldId
        ? { ...field, enabled: true, parameters: nativeParameters } : field),
      modifiers: working.document.modifiers.map(modifier => modifier.id === modifierId
        ? { ...modifier, region: region ?? undefined, influence_areas: draft.values.scope_mode === 'areas' ? areasToNative(draft.influenceAreas ?? [], scale) : undefined,
          enabled: true, mapping: { ...asRecord(modifier.mapping),
          min_output: draft.values.min_output, max_output: draft.values.max_output, strength: draft.values.strength, invert: draft.values.invert ?? false } } : modifier),
      metadata: { ...working.document.metadata, [OWNER]: { version: 1, field_id: fieldId, modifier_id: modifierId, bounds_mm: box, mm_per_unit: scale,
        ...(recorded?.rotation_modifier_id ? { rotation_modifier_id: recorded.rotation_modifier_id } : {}),
        field_ids: ids, field_domains: domains, source_mode: externalUnchanged ? 'existing' : 'owned', domain_mode: draft.existingFieldId || draft.explicitLinear ? 'explicit' : 'fitted' } },
    } }
}

/** Reset only this panel's declared configuration; source/user effects survive. */
export function resetLinearSizeDraft(draft: LinearSizeDraft, catalog: ParameterCatalog | null): LinearSizeDraft {
  const neutral = { ...draft.source, document: { ...draft.source.document,
    metadata: { ...draft.source.document.metadata, web_design_controls: undefined } } }
  const publicDefaults = groupFor(catalog, 'design', 'shape')
    ? { designValues: designValues(neutral, catalog), gridValues: gridValues(draft.source) ?? undefined, artboard: undefined } : {}
  if (draft.controlsOnly) return { ...draft, ...publicDefaults }
  const type = draft.fieldType ?? 'linear'
  return { ...selectSizeField(draft, type, catalog), ...publicDefaults, imageAsset: draft.imageAsset,
    fieldParameters: asRecord(addField(draft.source, type, catalog).dto.document.fields.at(-1)!.parameters)!,
    values: { ...linearSizeDefaults, ...linearRegionDefaults(draft.bounds), scope_mode: draft.values.scope_mode ?? 'global', scope_angle: 0, invert: false },
    influenceAreas: draft.influenceAreas?.map(area => ({ ...newInfluence(area.type, draft.bounds, catalog, []), id: area.id })),
  }
}
