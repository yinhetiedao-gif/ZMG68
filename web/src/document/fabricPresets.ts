import type { PatternDocumentDTO } from '../model/types'
import { addField } from './editor'
import { groupFor, validateParameter, type ParameterCatalog } from './parameterSchema'
import type { FabricBaseConfig } from './fabricBase'
import type { FabricPlacement, FabricUnitCell } from './fabricCell'
import type { FabricModifierType } from './fabricModifiers'
import { setDirectionalFabricHeight, setWaveFabricHeight, waveHeightField, setCenterFabricHeight, centerHeightDefaults } from './fabricModifiers'
import type { BoundsMM } from '../model/types'
import { setOriginalShape, isOriginalShape } from './fabricOriginal'

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

export const directionalFabricRecipe = {
  id: 'direction-gradient', version: 2, label: '方向渐变', units: 'mm', output_mode: 'cells_only',
  scope: ['output_mode', 'base', 'placement', 'unit_cell', 'height', 'scale.enabled', 'density.enabled', 'orientation.enabled'],
  base: { type: 'solid', thickness_mm: 0.6, margin_mm: 1 },
  placement: { mode: 'pattern_points', spacing_x_mm: 5, spacing_y_mm: 5 },
  cell: { type: 'pyramid', width_mm: 4.8, depth_mm: 4.8, height_mm: 3, size_mode: 'follow_pattern' },
  field: { type: 'linear', angle: 0, range: 'final_geometry_projection' },
  height: { min_height_mm: 2, max_height_mm: 6 },
  other_effects_enabled: false, random_seed: null,
} as const

export const waveFabricRecipe = {
  id: 'wave-height', version: 1, label: '波浪起伏', units: 'mm',
  scope: ['unit_cell', 'placement', 'height', 'owned_wave_field'],
  preserve: ['output_mode', 'base', 'scale', 'density', 'orientation', 'source', 'layout', '2d_modifiers'],
  placement: { mode: 'pattern_points', spacing_x_mm: 5, spacing_y_mm: 5 },
  cell: { type: 'pyramid', width_mm: 4.8, depth_mm: 4.8, height_mm: 3, size_mode: 'follow_pattern' },
  field: { type: 'wave', parameters: { wavelength: 36, angle: 0, phase: 0, amplitude: 1, offset: 0, invert: false } },
  height: { min_height_mm: 2, max_height_mm: 6 }, random_seed: null,
} as const

export const centerFabricRecipe = {
  id: 'center-height', version: 1, label: '中心隆起', units: 'mm',
  scope: ['height', 'owned_height_field'],
  field: { type: 'ring', radius: 0, falloff: 1, invert: false, range: 'half_final_geometry_diagonal_mm' },
  height: { min_height_mm: 2, max_height_mm: 6 }, random_seed: null,
} as const

/** The three height recipes preserve the selected shape, placement and output.
 * Explicit shape-replacement presets remain separate. */
export function applyFabricHeightRecipe(dto: PatternDocumentDTO, catalog: ParameterCatalog | null,
  bounds: BoundsMM | null, kind: 'wave' | 'directional' | 'center', uniformHeight: number): PatternDocumentDTO {
  const configured = isOriginalShape(dto) ? setOriginalShape(dto, catalog,
    (dto.document.metadata.fabric_config as any)?.original_shape ? {} : { height_mm: uniformHeight }) : dto
  const defaults = kind === 'center' ? centerHeightDefaults(configured, bounds) : null
  const next = kind === 'wave'
    ? setWaveFabricHeight(configured, catalog, { ...waveFabricRecipe.field.parameters, ...waveFabricRecipe.height })
    : kind === 'center' ? setCenterFabricHeight(configured, catalog, bounds, {
      center_x: Number(defaults!.center_x), center_y: Number(defaults!.center_y),
      range_mm: Number(defaults!.ring_width) / 2, ...centerFabricRecipe.height })
    : setDirectionalFabricHeight(configured, catalog, bounds, { angle: 0, ...directionalFabricRecipe.height })
  const id = (next.document.metadata.web_fabric_height_effect as any).field_id
  const field = next.document.fields.find(f => f.id === id)!
  return { ...next, document_revision: dto.document_revision + 1, document: { ...next.document,
    metadata: { ...next.document.metadata, web_fabric_recipe: {
      id: kind === 'wave' ? waveFabricRecipe.id : kind === 'center' ? centerFabricRecipe.id : directionalFabricRecipe.id,
      version: 1, units: 'mm', scope: ['height', 'owned_height_field'],
      shape_source: isOriginalShape(next) ? 'original' : 'unit_cell', field_id: id, field_type: field.type,
      field_parameters: { ...(field.parameters as object) },
      height: { ...((next.document.metadata.fabric_config as any).field_modifiers.height) }, random_seed: null,
    } } } }
}

export const applyOriginalHeightRecipe = applyFabricHeightRecipe

export function applyWaveFabricRecipe(dto: PatternDocumentDTO, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const recipe = waveFabricRecipe
  checkValues(catalog, 'fabric_cell', recipe.cell.type, recipe.cell)
  checkValues(catalog, 'fabric_placement', 'regular', recipe.placement)
  const original = dto.document.metadata.fabric_config as Record<string, any> | undefined
  const configured = { ...dto, document: { ...dto.document, metadata: { ...dto.document.metadata,
    fabric_config: { ...original, config_version: 1, shape_source: 'unit_cell',
      // Retain legacy effective output semantics as well as an explicit choice.
      output_mode: original?.output_mode ?? (original ? 'cells_with_base' : 'cells_only'),
      base: original?.base ?? { type: 'solid', thickness_mm: .6, margin_mm: 1 },
      unit_cell: { ...original?.unit_cell, ...recipe.cell },
      placement: { ...original?.placement, ...recipe.placement },
    },
  } } }
  const next = setWaveFabricHeight(configured, catalog, { ...recipe.field.parameters, ...recipe.height })
  const field = waveHeightField(next)!
  const config = next.document.metadata.fabric_config as Record<string, any>
  return { ...next, document_revision: dto.document_revision + 1,
    document: { ...next.document, metadata: { ...next.document.metadata, web_fabric_recipe: {
      id: recipe.id, version: recipe.version, units: recipe.units, scope: [...recipe.scope], preserve: [...recipe.preserve],
      field_id: field.id, field_type: 'wave', field_parameters: { ...(field.parameters as object) },
      height: { ...config.field_modifiers.height }, unit_cell: { ...config.unit_cell }, placement: { ...config.placement },
      output_mode: config.output_mode, base: { ...config.base }, random_seed: recipe.random_seed,
    } } } }
}

export function applyDirectionalFabricRecipe(dto: PatternDocumentDTO, catalog: ParameterCatalog | null,
  bounds: BoundsMM | null): PatternDocumentDTO {
  const recipe = directionalFabricRecipe
  checkValues(catalog, 'fabric_base', 'solid', recipe.base)
  checkValues(catalog, 'fabric_cell', 'pyramid', recipe.cell)
  checkValues(catalog, 'fabric_placement', 'regular', recipe.placement)
  const original = dto.document.metadata.fabric_config as Record<string, any> | undefined
  const modifiers = { ...original?.field_modifiers }
  for (const kind of ['scale', 'density', 'orientation']) {
    if (modifiers[kind]) modifiers[kind] = { ...modifiers[kind], enabled: false }
  }
  const configured = { ...dto, document: { ...dto.document, metadata: { ...dto.document.metadata,
    fabric_config: { ...original, config_version: 1, shape_source: 'unit_cell', output_mode: recipe.output_mode,
      base: { ...original?.base, ...recipe.base }, placement: { ...original?.placement, ...recipe.placement },
      unit_cell: { ...original?.unit_cell, ...recipe.cell }, field_modifiers: modifiers },
  } } }
  const next = setDirectionalFabricHeight(configured, catalog, bounds,
    { angle: recipe.field.angle, ...recipe.height })
  const field = next.document.fields.find(item => item.id === (next.document.metadata.web_fabric_height_effect as any).field_id)!
  return { ...next, document_revision: dto.document_revision + 1,
    document: { ...next.document, metadata: { ...next.document.metadata,
      web_fabric_recipe: { id: recipe.id, version: recipe.version, units: recipe.units,
        scope: [...recipe.scope], field_id: field.id, field_parameters: { ...(field.parameters as object) }, random_seed: null },
    } } }
}

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
      fabric_config: { ...config, ...(!previous ? { output_mode: 'cells_only' } : {}), config_version: 1, shape_source: 'unit_cell', base: { ...preset.base },
        placement: { ...preset.placement }, unit_cell: { ...preset.cell }, field_modifiers: modifiers } } } }
}
