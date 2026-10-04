import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'
import { fabricUnitCell } from './fabricCell'

export type FabricModifierType = 'height' | 'scale' | 'density' | 'orientation'
export interface FabricFieldModifier {
  enabled: boolean
  field_id: string
  [key: string]: ParameterValue
}
export const fabricModifierTypes: FabricModifierType[] = ['height', 'scale', 'density', 'orientation']
const supportedFields = new Set(['constant', 'linear', 'wave', 'ring', 'stripe', 'checker', 'spiral', 'noise', 'composite', 'image'])

export function availableFabricFields(dto: PatternDocumentDTO | null, modifierType?: FabricModifierType): { id: string; type: string }[] {
  const containsImage = (id: string, seen = new Set<string>()): boolean => {
    if (seen.has(id)) return false
    seen.add(id)
    const field = dto?.document.fields.find((item) => item.id === id)
    if (field?.type === 'image') return true
    if (field?.type !== 'composite') return false
    const parameters = field.parameters as Record<string, unknown> | undefined
    return ['input_a_field_id', 'input_b_field_id'].some((key) => containsImage(String(parameters?.[key]), seen))
  }
  return dto?.document.fields.filter((raw) => typeof raw.id === 'string' &&
    typeof raw.type === 'string' && supportedFields.has(raw.type) &&
    (modifierType !== 'orientation' || !containsImage(raw.id))).map((raw) =>
      ({ id: raw.id as string, type: raw.type as string })) ?? []
}

export function fabricFieldModifier(dto: PatternDocumentDTO | null, type: FabricModifierType): FabricFieldModifier | null {
  const config = dto?.document.metadata.fabric_config as Record<string, unknown> | undefined
  const modifiers = config?.field_modifiers as Record<string, unknown> | undefined
  const raw = modifiers?.[type]
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as FabricFieldModifier : null
}

function changed(dto: PatternDocumentDTO, type: FabricModifierType, modifier: FabricFieldModifier): PatternDocumentDTO {
  const config = dto.document.metadata.fabric_config as Record<string, unknown> | undefined
  if (!config || !fabricUnitCell(dto)) throw new Error('请先配置 Fabric Unit Cell。')
  const modifiers = { ...(config.field_modifiers as Record<string, unknown> | undefined), [type]: modifier }
  return { ...dto, document_revision: dto.document_revision + 1,
    document: { ...dto.document, metadata: { ...dto.document.metadata,
      fabric_config: { ...config, field_modifiers: modifiers } } } }
}

export function setFabricModifierEnabled(dto: PatternDocumentDTO, type: FabricModifierType,
  enabled: boolean, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const current = fabricFieldModifier(dto, type)
  if (!current && !enabled) return dto
  if (current?.enabled === enabled) return dto
  if (current) return changed(dto, type, { ...current, enabled })
  const fields = availableFabricFields(dto, type)
  if (!fields.length) throw new Error('请先在设计界面添加一个受支持的参数场。')
  const group = groupFor(catalog, 'fabric_modifier', type)
  if (!group) throw new Error('Python 参数定义尚未提供 Fabric Modifier。')
  return changed(dto, type, { enabled: true, field_id: fields[0].id,
    ...Object.fromEntries(group.parameters.map((parameter) => [parameter.id, parameter.default])) })
}

export function setFabricModifierField(dto: PatternDocumentDTO, type: FabricModifierType,
  fieldId: string): PatternDocumentDTO {
  const current = fabricFieldModifier(dto, type)
  if (!current?.enabled) throw new Error('请先启用 Fabric Modifier。')
  if (!availableFabricFields(dto, type).some((field) => field.id === fieldId))
    throw new Error('Fabric 参数场引用无效。')
  return current.field_id === fieldId ? dto : changed(dto, type, { ...current, field_id: fieldId })
}

export function updateFabricModifier(dto: PatternDocumentDTO, type: FabricModifierType,
  key: string, value: ParameterValue, catalog: ParameterCatalog | null): PatternDocumentDTO {
  const current = fabricFieldModifier(dto, type)
  if (!current?.enabled) throw new Error('请先启用 Fabric Modifier。')
  const definition = groupFor(catalog, 'fabric_modifier', type)?.parameters.find((item) => item.id === key)
  if (!definition || !validateParameter(definition, value) || typeof value !== 'number')
    throw new Error(`Fabric ${type} 参数 ${key} 无效。`)
  if (current[key] === value) return dto
  const next = { ...current, [key]: value }
  const pair = type === 'height' ? ['min_height_mm', 'max_height_mm']
    : type === 'scale' ? ['min_scale', 'max_scale']
      : type === 'orientation' ? ['min_angle_deg', 'max_angle_deg'] : null
  if (pair && Number(next[pair[0]]) > Number(next[pair[1]]))
    throw new Error('最小值不能大于最大值。')
  return changed(dto, type, next)
}
