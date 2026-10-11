import type { PatternDocumentDTO, BoundsMM } from '../model/types'
import { asRecord, PARAMETRIC_KEY, STACK_KEY } from './selectors'
import { millimetresPerUnit } from '../model/project'
import { updateGrid } from './editor'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue, type ParameterGroup } from './parameterSchema'

export const DESIGN_KEY = 'web_design_controls'
export interface InfluenceArea { id: string; type: 'line' | 'ellipse' | 'curve'; enabled: boolean; parameters: Record<string, number> }
/** Schema lengths are native document units; the Web controls show millimetres. */
export function physicalGroup(group: ParameterGroup | null, mm: number): ParameterGroup | null {
  return group ? { ...group, parameters: group.parameters.map(p => p.unit !== 'mm' ? p : { ...p,
    default: Number(p.default) * mm, min: p.min === null ? null : p.min * mm, max: p.max === null ? null : p.max * mm,
    step: p.step === null ? null : p.step * mm,
    slider_min: p.slider_min == null ? p.slider_min : p.slider_min * mm,
    slider_max: p.slider_max == null ? p.slider_max : p.slider_max * mm,
    slider_step: p.slider_step == null ? p.slider_step : p.slider_step * mm } ) } : null
}
export function designValues(dto: PatternDocumentDTO, catalog: ParameterCatalog | null): Record<string, ParameterValue> {
  const mm = millimetresPerUnit(dto.document) ?? 1, raw = asRecord(dto.document.metadata[DESIGN_KEY])
  return Object.fromEntries(['shape', 'random', 'stagger'].flatMap(type => (groupFor(catalog, 'design', type)?.parameters ?? [])
    .map(p => [p.id, (raw?.[p.id] ?? p.default) as ParameterValue]).map(([id, value]) =>
      [id, id === 'position_jitter' ? Number(value) * mm : value])))
}
export function gridValues(dto: PatternDocumentDTO) {
  const state = asRecord(dto.document.metadata[PARAMETRIC_KEY])
  if (state?.mode !== 'grid') return null
  const grid = asRecord(state.grid) ?? asRecord(state.model) ?? asRecord(state.parametric_model)
  const mm = millimetresPerUnit(dto.document) ?? 1
  return grid ? { rows: Number(grid.rows), columns: Number(grid.columns), spacing_x: Number(grid.spacing_x) * mm,
    spacing_y: Number(grid.spacing_y) * mm, base_spacing: Math.sqrt(Number(grid.spacing_x) * Number(grid.spacing_y)) * mm } : null
}
export function designCandidate(dto: PatternDocumentDTO, catalog: ParameterCatalog | null,
  values?: Record<string, ParameterValue>, grid?: Record<string, number>, board?: { width: number; height: number }): PatternDocumentDTO {
  const mm = millimetresPerUnit(dto.document)
  if (!mm) throw new Error('图案缺少有效毫米换算。')
  let result = dto
  if (grid) for (const key of ['rows', 'columns', 'spacing_x', 'spacing_y'])
    result = updateGrid(result, key, grid[key] / (key.startsWith('spacing') ? mm : 1), catalog)
  const metadata = { ...result.document.metadata }
  if (values) {
    for (const type of ['shape', 'random', 'stagger']) {
      const group = groupFor(catalog, 'design', type)
      if (!group) throw new Error('当前后端未提供图案控制参数，请重试参数目录。')
      for (const p of group.parameters) if (!validateParameter(p, p.unit === 'mm' ? Number(values[p.id]) / mm : values[p.id])) throw new Error(`图案控制参数无效：${p.label}`)
    }
    metadata[DESIGN_KEY] = { version: 1, ...values, position_jitter: Number(values.position_jitter) / mm }
    // Existing stable source snapshot prevents materialization/save from accumulating.
    const stack = asRecord(metadata[STACK_KEY])
    if (!Array.isArray(stack?.source_elements) || !stack.source_elements.length)
      metadata[STACK_KEY] = { version: 1, enabled: true, source_kind: 'imported_elements', ...stack,
        source_elements: structuredClone(dto.document.elements) }
  }
  if (board && (![board.width, board.height].every(v => Number.isFinite(v) && v > 0 && v <= 10000)))
    throw new Error('画板宽高需为0–10000 mm之间的正数。')
  return { ...result, document_revision: dto.document_revision, document: { ...result.document, metadata,
    canvas: board ? { ...result.document.canvas, width: board.width / mm, height: board.height / mm } : result.document.canvas } }
}
export function newInfluence(type: InfluenceArea['type'], bounds: BoundsMM, catalog: ParameterCatalog | null, areas: InfluenceArea[]): InfluenceArea {
  const group = groupFor(catalog, 'design', type)
  if (!group || areas.length >= 3) throw new Error('影响区最多3个，且必须有后端参数定义。')
  const cx = (bounds.min_x + bounds.max_x) / 2, cy = (bounds.min_y + bounds.max_y) / 2
  const length = Math.max(.1, bounds.width * .6), width = Math.max(.1, bounds.height * .5)
  const defaults = Object.fromEntries(group.parameters.map(p => [p.id, Number(p.default)]))
  const parameters = { ...defaults, ...type === 'curve' ? { x0: cx - length / 2, y0: cy, x1: cx, y1: cy - width / 2, x2: cx + length / 2, y2: cy, width, feather: Math.min(width / 4, 2) }
    : { x: cx, y: cy, length, width, angle: 0, feather: Math.min(width / 4, 2) } }
  let index = 1; while (areas.some(a => a.id === `area-${index}`)) index++
  return { id: `area-${index}`, type, enabled: true, parameters }
}
export function areasToNative(areas: InfluenceArea[], mm: number) {
  return areas.map(a => ({ ...a, parameters: Object.fromEntries(Object.entries(a.parameters).map(([key, value]) => [key, key === 'angle' ? value : value / mm])) }))
}
export function validateInfluenceAreas(areas: InfluenceArea[], mm: number, catalog: ParameterCatalog | null) {
  if (areas.length > 3 || new Set(areas.map(a => a.id)).size !== areas.length) throw new Error('影响区最多3个，身份不能重复。')
  for (const area of areas) {
    const group = physicalGroup(groupFor(catalog, 'design', area.type), mm)
    if (!group || group.parameters.some(p => !validateParameter(p, area.parameters[p.id]))) throw new Error('影响区参数不完整或超出后端Schema允许范围。')
    if (area.parameters.feather > area.parameters.width / 2) throw new Error('影响区边缘过渡不能超过半宽。')
    if (area.type === 'curve' && Math.hypot(area.parameters.x2 - area.parameters.x0, area.parameters.y2 - area.parameters.y0) < 1e-9)
      throw new Error('曲线轴起终点不能重合。')
  }
}
export function areasToMm(raw: unknown, mm: number): InfluenceArea[] | undefined {
  return Array.isArray(raw) ? raw.map(a => ({ ...a, parameters: Object.fromEntries(Object.entries(a.parameters).map(([key, value]) => [key, Number(value) * (key === 'angle' ? 1 : mm)])) })) : undefined
}
