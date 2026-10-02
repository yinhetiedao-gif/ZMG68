export type ParameterValue = number | boolean | string
export interface ParameterDefinition {
  id: string
  label: string
  type: 'number' | 'integer' | 'boolean' | 'select'
  default: ParameterValue
  value: ParameterValue
  min: number | null
  max: number | null
  step: number | null
  slider_min?: number | null
  slider_max?: number | null
  slider_step?: number | null
  unit: string
  options: { value: string; label: string }[]
  description?: string
  advanced?: boolean
}
export interface ParameterGroup { label: string; parameters: ParameterDefinition[] }
export interface ParameterCatalog {
  schema_version: string
  units: string
  definitions: Record<'layout' | 'field' | 'modifier', Record<string, ParameterGroup>> &
    { element?: Record<string, ParameterGroup>; fabric_base?: Record<string, ParameterGroup>;
      fabric_cell?: Record<string, ParameterGroup>; fabric_placement?: Record<string, ParameterGroup>;
      fabric_modifier?: Record<string, ParameterGroup> }
}

export function groupFor(catalog: ParameterCatalog | null, category: 'layout' | 'field' | 'modifier' | 'element' | 'fabric_base' | 'fabric_cell' | 'fabric_placement' | 'fabric_modifier',
  type: string): ParameterGroup | null {
  return catalog?.definitions?.[category]?.[type] ?? null
}

export function validateParameter(definition: ParameterDefinition, value: ParameterValue): boolean {
  if (definition.type === 'boolean') return typeof value === 'boolean'
  if (definition.type === 'select') return typeof value === 'string' &&
    definition.options.some((option) => option.value === value)
  if (typeof value !== 'number' || !Number.isFinite(value)) return false
  if (definition.type === 'integer' && !Number.isInteger(value)) return false
  if (definition.min !== null && value < definition.min) return false
  if (definition.max !== null && value > definition.max) return false
  return true
}

// Current Python catalogs supply these fields. The fallback only supports older
// contracts and uses the same categories; it never changes legal min/max.
export function recommendedSlider(definition: ParameterDefinition): { min: number; max: number; step: number } | null {
  const { min, max, step, type, unit, id } = definition
  if (type !== 'number' && type !== 'integer') return null
  if (definition.slider_min !== undefined || definition.slider_max !== undefined) {
    const lower = definition.slider_min
    const upper = definition.slider_max
    if (lower === null || upper === null || lower === undefined || upper === undefined) return null
    return { min: lower, max: upper, step: definition.slider_step ?? step ?? 1 }
  }
  if (min === null || max === null || id === 'seed') return null
  if (type === 'integer') return { min, max: Math.min(max, id === 'rows' || id === 'columns' ? 100 : 200), step: 1 }
  if (unit === 'mm') return { min: min < 0 ? Math.max(min, -300) : Math.max(min, min > 0 ? 1 : 0),
    max: Math.min(max, 300), step: step ?? 0.1 }
  if (unit === '°') return id === 'start_angle' || id === 'end_angle'
    ? { min: 0, max: 360, step: 1 } : { min: -180, max: 180, step: 1 }
  if (id === 'min_output' || id === 'max_output') return { min: Math.max(min, 0), max: Math.min(max, 3), step: 0.01 }
  if (id === 'falloff') return { min, max: Math.min(max, 1), step: 0.01 }
  if (id === 'turns') return { min, max: Math.min(max, 10), step: step ?? 0.1 }
  if (id === 'phase') return { min: Math.max(min, -10), max: Math.min(max, 10), step: step ?? 0.1 }
  if (id === 'contrast') return { min, max: Math.min(max, 3), step: 0.01 }
  return { min, max, step: step ?? 0.01 }
}
