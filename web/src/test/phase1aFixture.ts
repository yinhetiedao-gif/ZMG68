import type { PatternDocumentDTO, BoundsMM } from '../model/types'
import type { ParameterCatalog, ParameterGroup } from '../document/parameterSchema'
const group = (values: Record<string, number>): ParameterGroup => ({ label: '测试', parameters:
  Object.entries(values).map(([id, value]) => ({ id, label: id, default: value, value,
    type: 'number', min: -10000, max: 10000, step: .1, unit: '', options: [] })) })
export const phase1aCatalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: {}, modifier: {}, field: { linear: group({ angle: 0, start: 0, end: 100 }),
    ring: { label: 'Ring', parameters: [...group({ center_x: 0, center_y: 0, radius: 50, ring_width: 10, falloff: 1 }).parameters
      .map(p => ({ ...p, unit: p.id === 'falloff' ? '' : 'mm', min: p.id === 'ring_width' || p.id === 'falloff' ? .01 : p.id === 'radius' ? 0 : p.min })),
      { id: 'invert', label: 'invert', default: false, value: false, type: 'boolean', min: null, max: null, step: null, unit: '', options: [] }] },
    wave: { label: 'Wave', parameters: [...group({ angle: 0, wavelength: 30, phase: 0, amplitude: 1, offset: 0 }).parameters
      .map(p => p.id === 'wavelength' ? { ...p, min: .01, unit: 'mm' } : p),
      { id: 'invert', label: 'invert', default: false, value: false, type: 'boolean', min: null, max: null, step: null, unit: '', options: [] }] } },
  fabric_base: { solid: group({ thickness_mm: .6, margin_mm: 0 }) },
  fabric_cell: { pyramid: { ...group({ width_mm: 2, depth_mm: 2, height_mm: 3 }), parameters: [
    ...group({ width_mm: 2, depth_mm: 2, height_mm: 3 }).parameters,
    { id: 'size_mode', label: 'size_mode', default: 'follow_pattern', value: 'follow_pattern', type: 'select',
      min: null, max: null, step: null, unit: '', options: [{ value: 'fixed', label: 'fixed' }, { value: 'follow_pattern', label: 'follow' }] },
  ] } },
  fabric_placement: { regular: group({ spacing_x_mm: 5, spacing_y_mm: 5 }) },
  fabric_original: { original: group({ size_scale: 1, height_mm: 2 }) },
  fabric_modifier: { height: group({ min_height_mm: 1, max_height_mm: 5 }) },
} } as ParameterCatalog
export const phase1aBounds: BoundsMM = { min_x: 10, min_y: 20, max_x: 70, max_y: 80, width: 60, height: 60, units: 'mm' }
export function phase1aDocument(): PatternDocumentDTO {
  return { schema_version: '1.0', document_id: 'phase1a', document_revision: 3, assets: [], document: {
    schema_version: 1, canvas: { width: 60, height: 60, origin_x: 10, origin_y: 20, unit: 'mm', mm_per_unit: 1 },
    reference: {}, elements: [{ id: 'square', type: 'rect', x: 40, y: 50, width: 60, height: 60, visible: true, rotation: 0 }],
    groups: [], transforms: {}, fields: [], modifiers: [], metadata: { fabric_config: { config_version: 1,
      base: { type: 'solid', thickness_mm: .6, margin_mm: 0 },
      unit_cell: { type: 'pyramid', width_mm: 2, depth_mm: 2, height_mm: 3, size_mode: 'fixed' },
      placement: { mode: 'pattern_points', spacing_x_mm: 5, spacing_y_mm: 5 } } },
  } }
}
