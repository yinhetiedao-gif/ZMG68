import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'
import { fabricBase } from './fabricBase'
import { isOriginalShape } from './fabricOriginal'

export type UnitCellType = 'cylinder' | 'cone' | 'pyramid' | 'double_tower' | 'fin' | 'dome' | 'frustum' | 'hex_prism' | 'wedge' | 'cross' | 'ring'
export interface FabricUnitCell { type: UnitCellType; width_mm: number; depth_mm: number; height_mm: number;
  size_mode?: 'fixed' | 'follow_pattern'; shape_ratio?: number }
export interface FabricPlacement { mode?: 'area_fill' | 'pattern_points'; spacing_x_mm: number; spacing_y_mm: number }
export const unitCellChoices: { type: UnitCellType; label: string; path: string }[] = [
  { type: 'cylinder', label: '圆柱', path: 'M6 9 Q16 3 26 9 V24 Q16 30 6 24 Z M6 9 Q16 15 26 9' },
  { type: 'cone', label: '圆锥', path: 'M16 4 L5 25 Q16 31 27 25 Z' },
  { type: 'pyramid', label: '方锥', path: 'M16 4 L4 23 L16 29 L28 23 Z M16 4 V29' },
  { type: 'double_tower', label: '双塔', path: 'M4 8 H13 V27 H4 Z M19 8 H28 V27 H19 Z' },
  { type: 'fin', label: '鳍片', path: 'M4 25 L14 5 L28 21 L18 28 Z M14 5 L18 28' },
  { type: 'dome', label: '圆顶', path: 'M4 25 C4 0 28 0 28 25 Q16 30 4 25 Z' },
  { type: 'frustum', label: '圆台', path: 'M11 6 Q16 3 21 6 L28 25 Q16 31 4 25 Z M11 6 Q16 10 21 6' },
  { type: 'hex_prism', label: '六角柱', path: 'M4 10 L10 5 H22 L28 10 V24 L22 28 H10 L4 24 Z M4 10 L10 15 H22 L28 10 M10 15 V28 M22 15 V28' },
  { type: 'wedge', label: '楔形脊', path: 'M4 26 L25 5 V23 L10 29 Z M25 5 L10 29' },
  { type: 'cross', label: '十字凸台', path: 'M11 3 H21 V11 H29 V21 H21 V29 H11 V21 H3 V11 H11 Z' },
  { type: 'ring', label: '圆环', path: 'M3 16 A13 10 0 1 0 29 16 A13 10 0 1 0 3 16 M10 16 A6 4 0 1 0 22 16 A6 4 0 1 0 10 16' },
]
const types = unitCellChoices.map(item => item.type)

function config(dto: PatternDocumentDTO | null): Record<string, unknown> | null {
  if (!fabricBase(dto)) return null
  return dto!.document.metadata.fabric_config as Record<string, unknown>
}

export function fabricUnitCell(dto: PatternDocumentDTO | null): FabricUnitCell | null {
  if (isOriginalShape(dto)) return null
  const raw = config(dto)?.unit_cell
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const cell = raw as Record<string, unknown>
  return types.includes(cell.type as UnitCellType) ? cell as unknown as FabricUnitCell : null
}

export function fabricPlacement(dto: PatternDocumentDTO | null): FabricPlacement | null {
  const raw = config(dto)?.placement
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as FabricPlacement : null
}

function changed(dto: PatternDocumentDTO, cell: FabricUnitCell | null, placement: FabricPlacement | null) {
  const current = config(dto)
  if (!current) throw new Error('请先选择 Fabric Base。')
  const next = { ...current }
  if (cell && placement) { next.unit_cell = cell; next.placement = placement; next.shape_source = 'unit_cell' }
  else { delete next.unit_cell; delete next.placement; delete next.field_modifiers }
  return { ...dto, document_revision: dto.document_revision + 1,
    document: { ...dto.document, metadata: { ...dto.document.metadata, fabric_config: next } } }
}

export function setFabricUnitCellType(dto: PatternDocumentDTO, type: UnitCellType | 'none', catalog: ParameterCatalog | null) {
  const stored = config(dto)?.unit_cell as FabricUnitCell | undefined
  const current = fabricUnitCell(dto) ?? (isOriginalShape(dto) && stored && types.includes(stored.type) ? stored : null)
  if (type === 'none') return current ? changed(dto, null, null) : dto
  if (!types.includes(type)) throw new Error('Unit Cell 类型无效。')
  if (current?.type === type && !isOriginalShape(dto)) return dto
  const group = groupFor(catalog, 'fabric_cell', type)
  const placementGroup = groupFor(catalog, 'fabric_placement', 'regular')
  if (!catalog) throw new Error('单元参数尚未加载成功，请重试加载参数。')
  if (!group) throw new Error(`后端未提供单元 ${type} 的参数定义。`)
  if (!placementGroup && !fabricPlacement(dto)) throw new Error('后端未提供 regular 布点参数定义。')
  const cell = Object.fromEntries(group.parameters.map((parameter) => [parameter.id, parameter.default])) as unknown as FabricUnitCell
  cell.type = type
  if (current) { cell.width_mm = current.width_mm; cell.depth_mm = current.depth_mm; cell.height_mm = current.height_mm;
    cell.size_mode = current.size_mode ?? 'follow_pattern' }
  for (const parameter of group.parameters) {
    const value = cell[parameter.id as keyof FabricUnitCell]
    if (value === undefined || !validateParameter(parameter, value))
      throw new Error(`单元 ${type} 的参数 ${parameter.id} 不符合后端定义；已保留原单元。`)
  }
  const placement = fabricPlacement(dto) ?? Object.fromEntries(
    placementGroup!.parameters.map((parameter) => [parameter.id, parameter.default])) as unknown as FabricPlacement
  return changed(dto, cell, placement)
}

export function updateFabricUnitCell(dto: PatternDocumentDTO, section: 'cell' | 'placement', key: string,
  value: ParameterValue, catalog: ParameterCatalog | null) {
  const cell = fabricUnitCell(dto)
  const placement = fabricPlacement(dto)
  if (!cell || !placement) throw new Error('请先选择 Unit Cell。')
  const group = section === 'cell' ? groupFor(catalog, 'fabric_cell', cell.type)
    : groupFor(catalog, 'fabric_placement', 'regular')
  if (section === 'cell' && key === 'uniform_size_mm') {
    if (typeof value !== 'number') throw new Error('单元大小无效。')
    const depth = value * cell.depth_mm / cell.width_mm
    const widthDefinition = group?.parameters.find(item => item.id === 'width_mm')
    const depthDefinition = group?.parameters.find(item => item.id === 'depth_mm')
    if (!widthDefinition || !depthDefinition || !validateParameter(widthDefinition, value) || !validateParameter(depthDefinition, depth))
      throw new Error('单元大小超出合法范围。')
    if (value === cell.width_mm) return dto
    return changed(dto, { ...cell, width_mm: value, depth_mm: depth }, placement)
  }
  const definition = group?.parameters.find((item) => item.id === key)
  if (!definition || !validateParameter(definition, value) ||
    (key === 'size_mode' ? typeof value !== 'string' : typeof value !== 'number'))
    throw new Error(`Unit Cell 参数 ${key} 无效。`)
  if (section === 'cell') {
    if (cell[key as keyof FabricUnitCell] === value) return dto
    return changed(dto, { ...cell, [key]: value }, placement)
  }
  if (placement[key as keyof FabricPlacement] === value) return dto
  return changed(dto, cell, { ...placement, [key]: value })
}

export function setFabricPlacementMode(dto: PatternDocumentDTO, mode: 'area_fill' | 'pattern_points') {
  if (mode !== 'area_fill' && mode !== 'pattern_points') throw new Error('Fabric 布点方式无效。')
  const cell = fabricUnitCell(dto)
  const placement = fabricPlacement(dto)
  if (!cell || !placement || (placement.mode ?? 'area_fill') === mode) return dto
  return changed(dto, cell, { ...placement, mode })
}
