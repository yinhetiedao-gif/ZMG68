import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'
import { fabricUnitCell } from './fabricCell'
import { addField, fieldReferencedOutside } from './editor'
import type { BoundsMM } from '../model/types'
import { millimetresPerUnit } from '../model/project'

export type FabricModifierType = 'height' | 'scale' | 'density' | 'orientation'
export interface FabricFieldModifier {
  enabled: boolean
  field_id: string
  [key: string]: ParameterValue
}
export const fabricModifierTypes: FabricModifierType[] = ['height', 'scale', 'density', 'orientation']
const supportedFields = new Set(['constant', 'linear', 'wave', 'ring', 'stripe', 'checker', 'spiral', 'noise', 'composite', 'image', 'distance'])

export function availableFabricFields(dto: PatternDocumentDTO | null, modifierType?: FabricModifierType): { id: string; type: string }[] {
  void modifierType
  return dto?.document.fields.filter((raw) => typeof raw.id === 'string' &&
    typeof raw.type === 'string' && supportedFields.has(raw.type)).map((raw) =>
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
  if (!definition || !validateParameter(definition, value))
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

const HEIGHT_OWNER = 'web_fabric_height_effect'
type HeightOwner = { version: 1; field_id: string }
export function directionalHeightField(dto: PatternDocumentDTO | null) {
  const owner = dto?.document.metadata[HEIGHT_OWNER] as HeightOwner | undefined
  return owner?.version === 1 ? dto?.document.fields.find(field =>
    field.id === owner.field_id && field.type === 'linear') ?? null : null
}

/** Conservative reference scan: keep any field used outside this height consumer.
 * It also covers Composite and legacy stack metadata, including disabled users. */
function sharedOutsideHeight(dto: PatternDocumentDTO, id: string): boolean {
  return fieldReferencedOutside(dto, id, {
    metadataKeys: [HEIGHT_OWNER, 'web_fabric_recipe'], fabricConsumer: 'height',
  })
}

export function setUniformFabricHeight(dto: PatternDocumentDTO, catalog: ParameterCatalog | null) {
  return setFabricModifierEnabled(dto, 'height', false, catalog)
}

export function setDirectionalFabricHeight(dto: PatternDocumentDTO, catalog: ParameterCatalog | null,
  bounds: BoundsMM | null, edits: Partial<{ angle: number; min_height_mm: number; max_height_mm: number }> = {}): PatternDocumentDTO {
  if (!fabricUnitCell(dto)) throw new Error('请先配置 Fabric Unit Cell。')
  const previous = directionalHeightField(dto)
  const oldParameters = previous?.parameters as Record<string, unknown> | undefined
  const current = fabricFieldModifier(dto, 'height')
  const angle = edits.angle ?? Number(oldParameters?.angle ?? 0)
  const min = edits.min_height_mm ?? Number(current?.min_height_mm ?? 2)
  const max = edits.max_height_mm ?? Number(current?.max_height_mm ?? 6)
  for (const [category, type, key, value] of [
    ['field', 'linear', 'angle', angle], ['fabric_modifier', 'height', 'min_height_mm', min],
    ['fabric_modifier', 'height', 'max_height_mm', max],
  ] as const) {
    const definition = groupFor(catalog, category, type)?.parameters.find(item => item.id === key)
    if (!definition || !validateParameter(definition, value)) throw new Error('方向高度参数超出合法范围。')
  }
  if (min > max) throw new Error('最低高度不能大于最高高度。')
  const scale = millimetresPerUnit(dto.document)
  if (!scale) throw new Error('请先确认世界毫米比例。')
  const canvas = dto.document.canvas
  const box = bounds ?? { min_x: (canvas.origin_x ?? 0) * scale, min_y: (canvas.origin_y ?? 0) * scale,
    max_x: ((canvas.origin_x ?? 0) + canvas.width) * scale, max_y: ((canvas.origin_y ?? 0) + canvas.height) * scale }
  const radians = angle * Math.PI / 180
  const projections = [[box.min_x, box.min_y], [box.min_x, box.max_y],
    [box.max_x, box.min_y], [box.max_x, box.max_y]].map(([x, y]) => x * Math.cos(radians) + y * Math.sin(radians))
  const parameters = { angle, start: Math.min(...projections), end: Math.max(...projections) }
  if (!Number.isFinite(parameters.start) || !Number.isFinite(parameters.end) || parameters.start >= parameters.end)
    throw new Error('当前图案没有有效的方向范围。')
  let working = dto
  let id = previous?.id as string | undefined
  if (!id || sharedOutsideHeight(dto, id)) {
    const created = addField(dto, 'linear', catalog)
    working = created.dto; id = created.id
  }
  const metadata = working.document.metadata
  const config = metadata.fabric_config as Record<string, unknown>
  const fields = working.document.fields.map(field => field.id === id ? { ...field, enabled: true, parameters } : field)
  return { ...working, document_revision: dto.document_revision + 1,
    document: { ...working.document, fields, metadata: { ...metadata,
      [HEIGHT_OWNER]: { version: 1, field_id: id },
      fabric_config: { ...config, field_modifiers: {
        ...(config.field_modifiers as Record<string, unknown> | undefined),
        height: { enabled: true, field_id: id, min_height_mm: min, max_height_mm: max },
      } },
    } } }
}
