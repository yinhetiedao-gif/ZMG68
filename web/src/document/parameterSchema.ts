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
  unit: string
  options: { value: string; label: string }[]
  description?: string
  advanced?: boolean
}
export interface ParameterGroup { label: string; parameters: ParameterDefinition[] }
export interface ParameterCatalog {
  schema_version: string
  units: string
  definitions: Record<'layout' | 'field' | 'modifier', Record<string, ParameterGroup>>
}

export function groupFor(catalog: ParameterCatalog | null, category: 'layout' | 'field' | 'modifier',
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
