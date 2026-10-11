import basicGrid from '../examples/fixtures/basic-grid.pattern.json'
import { prepareProject, millimetresPerUnit } from '../model/project'
import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { updateGrid } from './editor'
import { asRecord } from './selectors'
import { designCandidate, designValues, gridValues, physicalGroup } from './designControls'
import { openLinearSize, selectSizeField, linearSizeCandidate, sizeFieldGroup, sizeFieldValues,
  linearSizeGroup, changeSizeFieldParameter, type LinearSizeDraft } from './linearSize'
import { groupFor, type ParameterCatalog, type ParameterGroup, type ParameterValue } from './parameterSchema'

export const PATTERN_PRESET_KEY = 'web_pattern_preset'
export type PatternPresetId = 'precision-stagger' | 'spectrum-fade' | 'diagonal-tide'
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
export function openPatternPreset(dto: PatternDocumentDTO, bounds: BoundsMM, id: PatternPresetId,
  catalog: ParameterCatalog | null, reset = false): LinearSizeDraft {
  const preset = patternPreset(id), opened = openLinearSize(dto, bounds)
  if (!preset.supportsCurrent && (patternPresetId(dto) !== id || !gridValues(dto)))
    throw new Error('精密错列只可编辑由此预设创建的 Grid 图案，不会重排当前导入作品。')
  if (patternPresetId(dto) === id && !reset) return { ...opened, presetId: id,
    ...!preset.field ? { controlsOnly: true, designValues: designValues(dto, catalog), gridValues: gridValues(dto)! } : {} }
  if (!preset.field) {
    const values = designValues(dto, catalog)
    return { ...opened, presetId: id, controlsOnly: true,
      designValues: { ...values, size_percent: 100, stagger: true },
      gridValues: { ...gridValues(dto)!, spacing_x: 6, spacing_y: 5.2, base_spacing: Math.sqrt(6 * 5.2) } }
  }
  let draft = selectSizeField(opened, preset.field, catalog)
  // Reset never touches public/random/artboard controls or other consumers.
  draft = { ...draft, presetId: id, controlsOnly: false, designValues: undefined,
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
  return draft
}

export function patternPresetCandidate(draft: LinearSizeDraft, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const result = linearSizeCandidate(draft, catalog)
  if (draft.presetId === '') {
    const metadata = { ...result.document.metadata }; delete metadata[PATTERN_PRESET_KEY]
    return { ...result, document: { ...result.document, metadata } }
  }
  if (!draft.presetId) return result
  const preset = patternPreset(draft.presetId)
  return { ...result, document: { ...result.document, metadata: { ...result.document.metadata,
    [PATTERN_PRESET_KEY]: { version: 1, id: preset.id, scope: preset.field ? 'owned_size_effect' : 'grid_spacing_stagger_size',
      units: 'mm' } } } }
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
  for (const [key, value] of Object.entries({ rows: 9, columns: 9, spacing_x: 6, spacing_y: preset.spacingY,
    element_width: preset.diameter, element_height: preset.diameter, offset_x: 30, offset_y: 30 }))
    working = updateGrid(working, key, value, catalog)
  const metadata = { ...working.document.metadata }
  delete metadata['xiaomang_pattern_lab.example_id']
  metadata[PATTERN_PRESET_KEY] = { version: 1, id, scope: preset.field ? 'owned_size_effect' : 'grid_spacing_stagger_size', units: 'mm' }
  working = { ...working, document_revision: dto.document_revision, document: { ...working.document, metadata } }
  const neutral = designValues(working, catalog)
  working = designCandidate(working, catalog, { ...neutral, size_percent: 100, aspect: 1, rotation: 0,
    size_random: 0, position_jitter: 0, rotation_random: 0, seed: 1, stagger: !preset.field })
  if (!preset.field) return working
  const bounds: BoundsMM = { min_x: 6 - preset.diameter / 2, max_x: 54 + preset.diameter / 2,
    min_y: 6 - preset.diameter / 2, max_y: 54 + preset.diameter / 2,
    width: 48 + preset.diameter, height: 48 + preset.diameter, units: 'mm' }
  return patternPresetCandidate(openPatternPreset(working, bounds, id, catalog, true), catalog)
}

/** The few primary controls are real Schema definitions; advanced parameters
 * continue through the same editor, draft and field graph. */
export function patternPresetControls(draft: LinearSizeDraft, catalog: ParameterCatalog | null): {
  group: ParameterGroup; values: Record<string, ParameterValue>
} {
  const preset = patternPreset(draft.presetId!), mm = millimetresPerUnit(draft.source.document) ?? 1
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
  return { group: { label: `${preset.title}关键参数`, parameters: preset.field === 'linear'
    ? mapping.parameters.filter(p => ['angle', 'min_output', 'max_output'].includes(p.id))
    : [...field.parameters.filter(p => ['field_wavelength', 'field_angle'].includes(p.id)),
      ...mapping.parameters.filter(p => p.id === 'max_output')] }, values: { ...draft.values, ...sizeFieldValues(draft, catalog) } }
}
export function changePatternPresetParameter(draft: LinearSizeDraft, catalog: ParameterCatalog | null,
  key: string, value: ParameterValue): LinearSizeDraft {
  if (key.startsWith('field_')) return changeSizeFieldParameter(draft, catalog, key, value)
  if (key.startsWith('preset_spacing_') && typeof value === 'number') {
    const grid = { ...draft.gridValues!, [key.slice(7)]: value }
    grid.base_spacing = Math.sqrt(grid.spacing_x * grid.spacing_y)
    return { ...draft, gridValues: grid }
  }
  return draft.controlsOnly ? { ...draft, designValues: { ...draft.designValues, [key]: value } }
    : { ...draft, values: { ...draft.values, [key]: value } }
}
