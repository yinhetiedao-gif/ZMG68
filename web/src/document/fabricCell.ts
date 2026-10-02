import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'
import { fabricBase } from './fabricBase'

export type UnitCellType = 'cylinder' | 'cone' | 'pyramid' | 'double_tower' | 'fin'
export interface FabricUnitCell { type: UnitCellType; width_mm: number; depth_mm: number; height_mm: number }
export interface FabricPlacement { mode?: 'area_fill' | 'pattern_points'; spacing_x_mm: number; spacing_y_mm: number }
const types: UnitCellType[] = ['cylinder', 'cone', 'pyramid', 'double_tower', 'fin']

function config(dto: PatternDocumentDTO | null): Record<string, unknown> | null {
  if (!fabricBase(dto)) return null
  return dto!.document.metadata.fabric_config as Record<string, unknown>
}

export function fabricUnitCell(dto: PatternDocumentDTO | null): FabricUnitCell | null {
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
  if (cell && placement) { next.unit_cell = cell; next.placement = placement }
  else { delete next.unit_cell; delete next.placement; delete next.field_modifiers }
  return { ...dto, document_revision: dto.document_revision + 1,
    document: { ...dto.document, metadata: { ...dto.document.metadata, fabric_config: next } } }
}

export function setFabricUnitCellType(dto: PatternDocumentDTO, type: UnitCellType | 'none', catalog: ParameterCatalog | null) {
  const current = fabricUnitCell(dto)
  if (type === 'none') return current ? changed(dto, null, null) : dto
  if (!types.includes(type)) throw new Error('Unit Cell 类型无效。')
  if (current?.type === type) return dto
  const group = groupFor(catalog, 'fabric_cell', type)
  const placementGroup = groupFor(catalog, 'fabric_placement', 'regular')
  if (!group || !placementGroup) throw new Error('Python 参数定义尚未提供 Unit Cell。')
  const cell = Object.fromEntries(group.parameters.map((parameter) => [parameter.id, parameter.default])) as unknown as FabricUnitCell
  cell.type = type
  if (current) { cell.width_mm = current.width_mm; cell.depth_mm = current.depth_mm; cell.height_mm = current.height_mm }
  const placement = fabricPlacement(dto) ?? Object.fromEntries(
    placementGroup.parameters.map((parameter) => [parameter.id, parameter.default])) as unknown as FabricPlacement
  return changed(dto, cell, placement)
}

export function updateFabricUnitCell(dto: PatternDocumentDTO, section: 'cell' | 'placement', key: string,
  value: ParameterValue, catalog: ParameterCatalog | null) {
  const cell = fabricUnitCell(dto)
  const placement = fabricPlacement(dto)
  if (!cell || !placement) throw new Error('请先选择 Unit Cell。')
  const group = section === 'cell' ? groupFor(catalog, 'fabric_cell', cell.type)
    : groupFor(catalog, 'fabric_placement', 'regular')
  const definition = group?.parameters.find((item) => item.id === key)
  if (!definition || !validateParameter(definition, value) || typeof value !== 'number')
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
