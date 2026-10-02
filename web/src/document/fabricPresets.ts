import type { PatternDocumentDTO } from '../model/types'
import { addField } from './editor'
import { groupFor, validateParameter, type ParameterCatalog } from './parameterSchema'
import type { FabricBaseConfig } from './fabricBase'
import type { FabricPlacement, FabricUnitCell } from './fabricCell'
import type { FabricModifierType } from './fabricModifiers'

type Binding = { field: 'wave' | 'linear' | 'noise'; values: Record<string, number> }
export interface FabricPreset {
  id: string
  label: string
  base: FabricBaseConfig
  placement: FabricPlacement
  cell: FabricUnitCell
  bindings: Partial<Record<FabricModifierType, Binding>>
}

export const fabricPresets: FabricPreset[] = [
  { id: 'soft-texture', label: 'Soft Texture', base: { type: 'solid', thickness_mm: 0.6, margin_mm: 0 },
    placement: { mode: 'pattern_points', spacing_x_mm: 5, spacing_y_mm: 5 },
    cell: { type: 'cylinder', width_mm: 2, depth_mm: 2, height_mm: 2 },
    bindings: { height: { field: 'wave', values: { min_height_mm: 1, max_height_mm: 3 } } } },
  { id: 'spike-surface', label: 'Spike Surface', base: { type: 'solid', thickness_mm: 0.8, margin_mm: 0 },
    placement: { mode: 'area_fill', spacing_x_mm: 5, spacing_y_mm: 5 },
    cell: { type: 'cone', width_mm: 2, depth_mm: 2, height_mm: 5 },
    bindings: { height: { field: 'wave', values: { min_height_mm: 2, max_height_mm: 7 } } } },
  { id: 'wave-textile', label: 'Wave Textile', base: { type: 'grid', thickness_mm: 0.6, margin_mm: 0,
    spacing_x_mm: 5, spacing_y_mm: 5, line_width_mm: 1 },
    placement: { mode: 'area_fill', spacing_x_mm: 5, spacing_y_mm: 5 },
    cell: { type: 'fin', width_mm: 2, depth_mm: 1, height_mm: 3 },
    bindings: { height: { field: 'wave', values: { min_height_mm: 1, max_height_mm: 6 } },
      orientation: { field: 'wave', values: { min_angle_deg: -45, max_angle_deg: 45 } } } },
  { id: 'dense-grid', label: 'Dense Grid', base: { type: 'grid', thickness_mm: 0.6, margin_mm: 0,
    spacing_x_mm: 4, spacing_y_mm: 4, line_width_mm: 1 },
    placement: { mode: 'area_fill', spacing_x_mm: 3, spacing_y_mm: 3 },
    cell: { type: 'pyramid', width_mm: 1.5, depth_mm: 1.5, height_mm: 2 },
    bindings: { scale: { field: 'linear', values: { min_scale: 0.7, max_scale: 1.2 } } } },
  { id: 'lightweight-fabric', label: 'Lightweight Fabric', base: { type: 'grid', thickness_mm: 0.5, margin_mm: 0,
    spacing_x_mm: 8, spacing_y_mm: 8, line_width_mm: 0.8 },
    placement: { mode: 'area_fill', spacing_x_mm: 8, spacing_y_mm: 8 },
    cell: { type: 'cylinder', width_mm: 1.5, depth_mm: 1.5, height_mm: 2 },
    bindings: { density: { field: 'noise', values: { threshold: 0.35 } } } },
]

function checkValues(catalog: ParameterCatalog | null, category: 'fabric_base' | 'fabric_cell' | 'fabric_placement' | 'fabric_modifier',
  type: string, values: Record<string, unknown>) {
  const group = groupFor(catalog, category, type)
  if (!group) throw new Error(`Python 参数定义缺少 ${category}/${type}。`)
  for (const definition of group.parameters) {
    if (!validateParameter(definition, values[definition.id] as number))
      throw new Error(`预设参数 ${type}.${definition.id} 无效。`)
  }
}

export function applyFabricPreset(dto: PatternDocumentDTO, presetId: string,
  catalog: ParameterCatalog | null): PatternDocumentDTO {
  const preset = fabricPresets.find((item) => item.id === presetId)
  if (!preset) throw new Error('Fabric 预设不存在。')
  checkValues(catalog, 'fabric_base', preset.base.type, { ...preset.base })
  checkValues(catalog, 'fabric_cell', preset.cell.type, { ...preset.cell })
  checkValues(catalog, 'fabric_placement', 'regular', { ...preset.placement })
  if (preset.base.type === 'grid' && preset.base.line_width_mm! > Math.min(preset.base.spacing_x_mm!, preset.base.spacing_y_mm!))
    throw new Error('Fabric 预设网格线宽超过间距。')
  let working = dto
  const modifiers: Record<string, unknown> = {}
  for (const [kind, binding] of Object.entries(preset.bindings) as [FabricModifierType, Binding][]) {
    checkValues(catalog, 'fabric_modifier', kind, binding.values)
    let field = working.document.fields.find((item) => item.type === binding.field && item.enabled !== false)
    if (!field) {
      const created = addField(working, binding.field, catalog)
      working = created.dto
      field = working.document.fields.find((item) => item.id === created.id)
    }
    modifiers[kind] = { enabled: true, field_id: field!.id, ...binding.values }
  }
  const previous = working.document.metadata.fabric_config
  const config = previous && typeof previous === 'object' && !Array.isArray(previous)
    ? previous as Record<string, unknown> : {}
  return { ...working, document_revision: dto.document_revision + 1,
    document: { ...working.document, metadata: { ...working.document.metadata,
      fabric_config: { ...config, config_version: 1, base: { ...preset.base },
        placement: { ...preset.placement }, unit_cell: { ...preset.cell }, field_modifiers: modifiers } } } }
}
