import basicGrid from '../examples/fixtures/basic-grid.pattern.json'
import { prepareProject, millimetresPerUnit } from '../model/project'
import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { updateGrid } from './editor'
import { asRecord, STACK_KEY } from './selectors'
import { openRadialSize, radialSizeCandidate, radialSizeGroup, radialSizeDefaults, type RadialSizeDraft } from './radialSize'
import { designCandidate, designValues, gridValues, physicalGroup } from './designControls'
import { openLinearSize, selectSizeField, linearSizeCandidate, sizeFieldGroup, sizeFieldValues,
  linearSizeGroup, linearSizeOwner, changeSizeFieldParameter, type LinearSizeDraft } from './linearSize'
import { groupFor, type ParameterCatalog, type ParameterGroup, type ParameterValue } from './parameterSchema'

export const PATTERN_PRESET_KEY = 'web_pattern_preset'
export type PatternPresetId = 'precision-stagger' | 'spectrum-fade' | 'diagonal-tide' | 'local-breath' | 'coral-grains' | 'ripple-center'
export type PatternPresetDraft = LinearSizeDraft | RadialSizeDraft
export const patternPresets = [
  { id: 'precision-stagger', title: '精密错列', description: '均匀圆点交错排列，调整大小与双轴间距。',
    supportsCurrent: false, field: null, diameter: 3.2, spacingY: 5.2,
    scope: '双轴间距、错列及单元尺寸；仅创建新图案，不替换导入作品的排列。' },
  { id: 'spectrum-fade', title: '光谱渐隐', description: '沿一个方向逐渐改变大小，保留图形中心。',
    supportsCurrent: true, field: 'linear', diameter: 3.4, spacingY: 6,
    scope: '替换尺寸快捷入口管理的尺寸层、专用驱动及本层范围；保留其他效果、原图和布局。' },
  { id: 'diagonal-tide', title: '斜向潮汐', description: '连续大小起伏形成斜向波带，位置保持不变。',
    supportsCurrent: true, field: 'wave', diameter: 3.4, spacingY: 6,
    scope: '替换尺寸快捷入口管理的尺寸层、专用驱动及本层范围；保留其他效果、原图和布局。' },
  { id: 'local-breath', title: '局部呼吸', description: '椭圆或曲线内柔和改变大小，外围完整保持。',
    supportsCurrent: true, field: 'constant', diameter: 3.2, spacingY: 6,
    scope: '受管尺寸层、专用固定场及最多3个影响区；重叠取最大权重，共用一个倍率。' },
  { id: 'coral-grains', title: '珊瑚微粒', description: '连续噪声形成自然颗粒；新建使用稳定随机椭圆，不是散点算法。',
    supportsCurrent: true, field: 'noise', diameter: 2.8, spacingY: 4.6,
    scope: '默认只替换受管尺寸效果；主动调整错位/旋转才改变位置/方向。保留原图与布局。' },
  { id: 'ripple-center', title: '涟心扩散', description: '中心突出、外围缩小，保持原图形中心和排列。',
    supportsCurrent: true, field: null, diameter: 3.2, spacingY: 6,
    scope: '仅管理预设专用径向尺寸层；半径之外保持外围倍率，不是放射布局或环带。' },
] as const
export function patternPreset(id: string) {
  const preset = patternPresets.find(p => p.id === id)
  if (!preset) throw new Error('此图案预设不存在。')
  return preset
}
export function patternPresetId(dto: PatternDocumentDTO | null): PatternPresetId | null {
  const record = asRecord(dto?.document.metadata[PATTERN_PRESET_KEY])
  return record?.version === 1 && patternPresets.some(p => p.id === record.id) ? record.id as PatternPresetId : null
}

/** Open the existing candidate editor, not another parameter/geometry engine.
 * A different recipe resets only its declared scope. Same-recipe editing reads
 * the stored graph, including changes made in the advanced editor. */
export function openPatternPreset(dto: PatternDocumentDTO, bounds: BoundsMM, id: 'ripple-center', catalog: ParameterCatalog | null, reset?: boolean): RadialSizeDraft
export function openPatternPreset(dto: PatternDocumentDTO, bounds: BoundsMM, id: Exclude<PatternPresetId, 'ripple-center'>, catalog: ParameterCatalog | null, reset?: boolean): LinearSizeDraft
export function openPatternPreset(dto: PatternDocumentDTO, bounds: BoundsMM, id: PatternPresetId, catalog: ParameterCatalog | null, reset?: boolean): PatternPresetDraft
export function openPatternPreset(dto: PatternDocumentDTO, bounds: BoundsMM, id: PatternPresetId,
  catalog: ParameterCatalog | null, reset = false): PatternPresetDraft {
  const preset = patternPreset(id), same = patternPresetId(dto) === id
  const record = asRecord(dto.document.metadata[PATTERN_PRESET_KEY])
  const saved = same ? asRecord(record?.bounds_mm) : null
  const mm = millimetresPerUnit(dto.document) ?? 1, factor = mm / Number(record?.mm_per_unit ?? mm)
  if (saved && (!Number.isFinite(factor) || factor <= 0)) throw new Error('预设初始化范围的毫米换算无效。')
  const box: BoundsMM = saved ? { min_x: Number(saved.min_x) * factor, min_y: Number(saved.min_y) * factor,
    max_x: Number(saved.max_x) * factor, max_y: Number(saved.max_y) * factor,
    width: Number(saved.width) * factor, height: Number(saved.height) * factor, units: 'mm' } : bounds
  if (id === 'ripple-center') {
    const radial = openRadialSize(dto, box, typeof record?.radial_layer_id === 'string' ? record.radial_layer_id : null)
    return { ...radial, presetId: id, values: same && !reset ? radial.values : { ...radialSizeDefaults(box), min_scale: 1.25, max_scale: .65 } }
  }
  const opened = openLinearSize(dto, bounds)
  if (!preset.supportsCurrent && (patternPresetId(dto) !== id || !gridValues(dto)))
    throw new Error('精密错列只可编辑由此预设创建的 Grid 图案，不会重排当前导入作品。')
  if (same && !reset) return { ...opened, presetId: id,
    ...id === 'coral-grains' && asRecord(dto.document.metadata.web_design_controls) ? { designValues: designValues(dto, catalog) } : {},
    ...!preset.field ? { controlsOnly: true, designValues: designValues(dto, catalog), gridValues: gridValues(dto)! } : {} }
  if (!preset.field) {
    const values = designValues(dto, catalog)
    return { ...opened, presetId: id, controlsOnly: true,
      designValues: { ...values, size_percent: 100, stagger: true },
      gridValues: { ...gridValues(dto)!, spacing_x: 6, spacing_y: 5.2, base_spacing: Math.sqrt(6 * 5.2) } }
  }
  let draft = selectSizeField(opened, preset.field, catalog)
  // Reset never touches public/random/artboard controls or other consumers.
  draft = { ...draft, bounds: box, presetId: id, controlsOnly: false, designValues: undefined,
    gridValues: undefined, artboard: undefined, existingFieldId: undefined, explicitLinear: false,
    influenceAreas: undefined, imageAsset: undefined,
    values: { ...draft.values, angle: preset.field === 'linear' ? 0 : 35,
      min_output: preset.field === 'linear' ? .55 : .65, max_output: 1.15,
      strength: 1, invert: false, scope_mode: 'global' } }
  if (preset.field === 'wave') {
    const group = groupFor(catalog, 'field', 'wave'), mm = millimetresPerUnit(dto.document)
    if (!group || !mm) throw new Error('缺少波浪参数定义或有效毫米映射。')
    draft.fieldParameters = { ...Object.fromEntries(group.parameters.map(p => [p.id, p.default])),
      angle: 35, wavelength: 23 / mm, phase: 0, amplitude: 1, offset: 0, invert: false }
  }
  if (preset.field === 'constant') {
    const cx = (box.min_x + box.max_x) / 2, cy = (box.min_y + box.max_y) / 2
    const w = box.width, h = box.height, width = Math.max(.1, h * .43)
    draft.fieldParameters = { value: .5 }
    draft.values = { ...draft.values, min_output: 1.30, max_output: 1.30, scope_mode: 'areas' }
    draft.influenceAreas = [
      { id: 'area-1', type: 'ellipse', enabled: true, parameters: { x: cx - w * .08, y: cy, angle: -20,
        length: Math.max(.1, w * .59), width, feather: Math.min(4, width / 4) } },
      { id: 'area-2', type: 'curve', enabled: false, parameters: { x0: cx - w * .32, y0: cy + h * .24,
        x1: cx, y1: cy - h * .36, x2: cx + w * .36, y2: cy + h * .20,
        width: Math.max(.1, h * .20), feather: Math.min(3, h * .05) } },
    ]
    draft.selectedArea = 'area-1'
  }
  if (preset.field === 'noise') {
    const mm = millimetresPerUnit(dto.document)
    if (!mm) throw new Error('缺少有效毫米映射。')
    draft.fieldParameters = { scale: 14 / mm, strength: 1, seed: 27, offset_x: 0, offset_y: 0, octaves: 3, contrast: 1.5, invert: false }
    draft.values = { ...draft.values, min_output: .60, max_output: 1.12 }
    // A current artwork keeps all public controls; only declared random keys
    // owned by a previously created coral recipe are reset.
    const values = designValues(dto, catalog), before = asRecord(record?.random_before), after = asRecord(record?.random_after)
    draft.designValues = asRecord(dto.document.metadata.web_design_controls) ? { ...values } : undefined
    if (same && reset && before && after) for (const key of Object.keys(before))
      if (values[key] === (key === 'position_jitter' ? Number(after[key]) * mm : after[key])) {
        draft.designValues ??= { ...values }
        draft.designValues[key] = key === 'seed' ? 27 : key === 'size_random' ? .10 : key === 'position_jitter' ? .35 : 35
      }
  }
  return draft
}

/** Disable only a departing preset's actual owned layer. Never delete fields
 * that may be referenced elsewhere, or change a user's independent radial layer. */
function preparePresetSwitch(dto: PatternDocumentDTO, next?: string): PatternDocumentDTO {
  const old = patternPresetId(dto)
  if (!next || !old || old === next) return dto
  const record = asRecord(dto.document.metadata[PATTERN_PRESET_KEY])!, stack = asRecord(dto.document.metadata[STACK_KEY])
  let metadata = { ...dto.document.metadata }, modifiers = dto.document.modifiers
  if (old === 'ripple-center' && Array.isArray(stack?.modifiers)) metadata[STACK_KEY] = { ...stack,
    modifiers: stack.modifiers.map(item => asRecord(item)?.id === record.radial_layer_id ? { ...item, enabled: false } : item) }
  if (next === 'ripple-center' && patternPreset(old).field) {
    const owned = linearSizeOwner(dto)
    if (owned && owned.field.type === patternPreset(old).field)
      modifiers = modifiers.map(m => m.id === owned.modifier.id ? { ...m, enabled: false } : m)
  }
  if (old === 'coral-grains') {
    const before = asRecord(record.random_before), after = asRecord(record.random_after), current = asRecord(metadata.web_design_controls)
    if (before && after && current) {
      const values = { ...current }
      for (const key of Object.keys(before)) if (current[key] === after[key]) values[key] = before[key]
      metadata.web_design_controls = values
    }
  }
  return { ...dto, document: { ...dto.document, metadata, modifiers } }
}
export function patternPresetCandidate(draft: PatternPresetDraft, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const source = preparePresetSwitch(draft.source, draft.presetId)
  const result = draft.kind === 'radial' ? radialSizeCandidate({ ...draft, source }, catalog) : linearSizeCandidate({ ...draft, source }, catalog)
  if (draft.presetId === '') {
    const metadata = { ...result.document.metadata }; delete metadata[PATTERN_PRESET_KEY]
    return { ...result, document: { ...result.document, metadata } }
  }
  if (!draft.presetId) return result
  const preset = patternPreset(draft.presetId)
  const previous = asRecord(draft.source.document.metadata[PATTERN_PRESET_KEY]), old = patternPresetId(draft.source)
  const layers = asRecord(result.document.metadata[STACK_KEY])?.modifiers as unknown[] | undefined
  const radialId = draft.kind === 'radial' ? draft.managedLayerId ?? layers?.map(asRecord).filter(l => l?.type === 'size' && asRecord(l.parameters)?.mode === 'radial').at(-1)?.id : previous?.radial_layer_id
  let random: Record<string, unknown> = {}
  if (preset.id === 'coral-grains' && draft.kind === 'linear') {
    const before = designValues(draft.source, catalog), after = designValues(result, catalog)
    const mm = millimetresPerUnit(result.document)!
    const ownedBefore = old === preset.id ? { ...asRecord(previous?.random_before) } : {}
    const ownedAfter = old === preset.id ? { ...asRecord(previous?.random_after) } : {}
    for (const key of ['seed', 'size_random', 'position_jitter', 'rotation_random']) {
      if (after[key] !== before[key] && !(key in ownedBefore)) ownedBefore[key] = key === 'position_jitter' ? Number(before[key]) / mm : before[key]
      if (key in ownedBefore) ownedAfter[key] = key === 'position_jitter' ? Number(after[key]) / mm : after[key]
    }
    random = { random_before: ownedBefore, random_after: ownedAfter }
  }
  return { ...result, document: { ...result.document, metadata: { ...result.document.metadata,
    [PATTERN_PRESET_KEY]: { version: 1, id: preset.id, scope: preset.id === 'ripple-center' ? 'owned_radial_size' : preset.field ? 'owned_size_effect' : 'grid_spacing_stagger_size',
      units: 'mm', ...['local-breath', 'coral-grains', 'ripple-center'].includes(preset.id) ? { bounds_mm: draft.bounds, mm_per_unit: millimetresPerUnit(result.document) } : {},
      ...(radialId ? { radial_layer_id: radialId } : {}), ...random } } } }
}

/** Explicit advanced driver changes become a custom effect, not a mislabeled
 * preset. Only the identity is removed on Apply; no fields/effects are deleted. */
export function selectPatternPresetDriver(draft: LinearSizeDraft, type: string, catalog: ParameterCatalog | null, existingId?: string) {
  const next = selectSizeField(draft, type, catalog, existingId)
  const id = draft.presetId || patternPresetId(draft.source)
  return id && (existingId || patternPreset(id).field !== type) ? { ...next, presetId: '' } : next
}

/** Reuse the formal Grid fixture. Python generates all cells; no JS array math. */
export function createPatternPreset(id: PatternPresetId, documentId: string, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const preset = patternPreset(id), dto = prepareProject(JSON.stringify(basicGrid), documentId).dto
  let working = dto
  const coral = id === 'coral-grains', spacing = coral ? 4.6 : 6
  for (const [key, value] of Object.entries({ rows: coral ? 11 : 9, columns: coral ? 11 : 9, spacing_x: spacing, spacing_y: preset.spacingY,
    element_width: preset.diameter, element_height: coral ? 1.7 : preset.diameter, offset_x: 30, offset_y: 30 }))
    working = updateGrid(working, key, value, catalog)
  const metadata = { ...working.document.metadata }
  delete metadata['xiaomang_pattern_lab.example_id']
  metadata[PATTERN_PRESET_KEY] = { version: 1, id, scope: preset.field ? 'owned_size_effect' : 'grid_spacing_stagger_size', units: 'mm' }
  working = { ...working, document_revision: dto.document_revision, document: { ...working.document, metadata } }
  const neutral = designValues(working, catalog)
  working = designCandidate(working, catalog, { ...neutral, size_percent: 100, aspect: 1, rotation: 0,
    size_random: 0, position_jitter: 0, rotation_random: 0, seed: 1, stagger: id === 'precision-stagger' })
  if (id === 'precision-stagger') return working
  if (coral) {
    // Existing source aspect transform produces real ellipses without replacing
    // imported contours. The public size keeps the intended 2.8 x 1.7 baseline.
    working = designCandidate(working, catalog, { ...designValues(working, catalog), aspect: 2.8 / 1.7,
      size_percent: 100 * Math.sqrt(1.7 / 2.8) })
    working = updateGrid(working, 'element_height', 2.8, catalog)
    working = { ...working, document_revision: dto.document_revision }
  }
  const extent = coral ? 23 : 24
  const bounds: BoundsMM = { min_x: 30 - extent - preset.diameter / 2, max_x: 30 + extent + preset.diameter / 2,
    min_y: 30 - extent - (coral ? 1.7 : preset.diameter) / 2, max_y: 30 + extent + (coral ? 1.7 : preset.diameter) / 2,
    width: extent * 2 + preset.diameter, height: extent * 2 + (coral ? 1.7 : preset.diameter), units: 'mm' }
  let draft = openPatternPreset(working, bounds, id, catalog, true)
  if (coral && draft.kind === 'linear') draft = { ...draft, designValues: { ...designValues(working, catalog),
    size_random: .10, position_jitter: .35, rotation_random: 35, seed: 27 } }
  return patternPresetCandidate(draft, catalog)
}

/** The few primary controls are real Schema definitions; advanced parameters
 * continue through the same editor, draft and field graph. */
export function patternPresetControls(draft: PatternPresetDraft, catalog: ParameterCatalog | null): {
  group: ParameterGroup; values: Record<string, ParameterValue>
} {
  const preset = patternPreset(draft.presetId!), mm = millimetresPerUnit(draft.source.document) ?? 1
  if (draft.kind === 'radial') {
    const group = radialSizeGroup(catalog, draft.source, draft.bounds)
    if (!group) throw new Error('缺少径向尺寸预设参数定义。')
    return { group: { ...group, parameters: group.parameters.filter(p => ['radius', 'min_scale', 'max_scale'].includes(p.id)) }, values: { ...draft.values } }
  }
  if (!preset.field) {
    const shape = groupFor(catalog, 'design', 'shape'), grid = physicalGroup(groupFor(catalog, 'layout', 'grid'), mm)
    const size = shape?.parameters.find(p => p.id === 'size_percent')
    const spacing = grid?.parameters.filter(p => ['spacing_x', 'spacing_y'].includes(p.id))
    if (!size || spacing?.length !== 2) throw new Error('缺少图案预设参数定义。')
    return { group: { label: '精密错列关键参数', parameters: [size,
      ...spacing.map(p => ({ ...p, id: `preset_${p.id}` }))] }, values: { size_percent: draft.designValues?.size_percent ?? 100,
      preset_spacing_x: draft.gridValues?.spacing_x ?? 6, preset_spacing_y: draft.gridValues?.spacing_y ?? 5.2 } }
  }
  const mapping = linearSizeGroup(catalog, draft), field = sizeFieldGroup(catalog, draft)
  if (!mapping || !field) throw new Error('缺少尺寸预设参数定义。')
  if (preset.id === 'local-breath') {
    const selected = draft.influenceAreas?.find(a => a.id === draft.selectedArea) ?? draft.influenceAreas?.[0]
    const area = physicalGroup(groupFor(catalog, 'design', selected?.type ?? 'ellipse'), mm)
    const ratio = mapping.parameters.find(p => p.id === 'max_output')!
    return { group: { label: '局部呼吸关键参数', parameters: [{ ...ratio, id: 'preset_ratio', label: '局部尺寸倍率' },
      ...(area?.parameters.filter(p => ['width', 'feather'].includes(p.id)).map(p => ({ ...p, id: `preset_area_${p.id}`,
        label: p.id === 'width' ? selected?.type === 'ellipse' ? '影响宽度（短轴直径）' : '影响宽度' : p.label })) ?? [])] },
      values: { preset_ratio: draft.values.max_output, preset_area_width: selected?.parameters.width ?? 1, preset_area_feather: selected?.parameters.feather ?? 0 } }
  }
  if (preset.id === 'coral-grains') {
    const random = physicalGroup(groupFor(catalog, 'design', 'random'), mm)
    return { group: { label: '珊瑚微粒关键参数', parameters: [...field.parameters.filter(p => p.id === 'field_scale'),
      ...mapping.parameters.filter(p => ['min_output', 'max_output'].includes(p.id)),
      ...(random?.parameters.filter(p => p.id === 'position_jitter').map(p => ({ ...p, id: 'preset_jitter', label: '错位幅度（改变位置）' })) ?? [])] },
      values: { ...draft.values, ...sizeFieldValues(draft, catalog), preset_jitter: draft.designValues?.position_jitter ?? designValues(draft.source, catalog).position_jitter } }
  }
  return { group: { label: `${preset.title}关键参数`, parameters: preset.field === 'linear'
    ? mapping.parameters.filter(p => ['angle', 'min_output', 'max_output'].includes(p.id))
    : [...field.parameters.filter(p => ['field_wavelength', 'field_angle'].includes(p.id)),
      ...mapping.parameters.filter(p => p.id === 'max_output')] }, values: { ...draft.values, ...sizeFieldValues(draft, catalog) } }
}
export function changePatternPresetParameter(draft: LinearSizeDraft, catalog: ParameterCatalog | null, key: string, value: ParameterValue): LinearSizeDraft
export function changePatternPresetParameter(draft: PatternPresetDraft, catalog: ParameterCatalog | null, key: string, value: ParameterValue): PatternPresetDraft
export function changePatternPresetParameter(draft: PatternPresetDraft, catalog: ParameterCatalog | null,
  key: string, value: ParameterValue): PatternPresetDraft {
  if (draft.kind === 'radial') return typeof value === 'number' ? { ...draft, values: { ...draft.values, [key]: value } } : draft
  if (key === 'preset_ratio' && typeof value === 'number') return { ...draft, values: { ...draft.values, min_output: value, max_output: value } }
  if (key.startsWith('preset_area_') && typeof value === 'number') {
    const id = draft.selectedArea ?? draft.influenceAreas?.[0]?.id
    return { ...draft, influenceAreas: draft.influenceAreas?.map(a => a.id === id ? { ...a, parameters: { ...a.parameters, [key.slice(12)]: value } } : a) }
  }
  if (key === 'preset_jitter') return { ...draft, designValues: { ...designValues(draft.source, catalog), ...draft.designValues, position_jitter: value } }
  if (key.startsWith('field_')) return changeSizeFieldParameter(draft, catalog, key, value)
  if (key.startsWith('preset_spacing_') && typeof value === 'number') {
    const grid = { ...draft.gridValues!, [key.slice(7)]: value }
    grid.base_spacing = Math.sqrt(grid.spacing_x * grid.spacing_y)
    return { ...draft, gridValues: grid }
  }
  return draft.controlsOnly ? { ...draft, designValues: { ...draft.designValues, [key]: value } }
    : { ...draft, values: { ...draft.values, [key]: value } }
}
