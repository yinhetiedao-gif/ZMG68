import type { PatternDocumentDTO } from '../model/types'
import { groupFor, validateParameter, type ParameterCatalog, type ParameterValue } from './parameterSchema'

export type FabricBaseType = 'solid' | 'grid'
export interface FabricBaseConfig {
  type: FabricBaseType
  thickness_mm: number
  margin_mm: number
  spacing_x_mm?: number
  spacing_y_mm?: number
  line_width_mm?: number
}

export function fabricBase(dto: PatternDocumentDTO | null): FabricBaseConfig | null {
  const raw = dto?.document.metadata.fabric_config
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const config = raw as Record<string, unknown>
  if (config.config_version !== 1 || !config.base || typeof config.base !== 'object') return null
  const base = config.base as Record<string, unknown>
  return base.type === 'solid' || base.type === 'grid' ? base as unknown as FabricBaseConfig : null
}

function validBase(base: FabricBaseConfig): void {
  if (base.type === 'grid' && (base.line_width_mm ?? 0) > Math.min(base.spacing_x_mm ?? 0, base.spacing_y_mm ?? 0)) {
    throw new Error('网格线宽不能大于水平或垂直间距。')
  }
}

function changed(dto: PatternDocumentDTO, base: FabricBaseConfig | null): PatternDocumentDTO {
  const metadata = { ...dto.document.metadata }
  if (base) metadata.fabric_config = { config_version: 1, base }
  else delete metadata.fabric_config
  return { ...dto, document_revision: dto.document_revision + 1,
    document: { ...dto.document, metadata } }
}

export function setFabricBaseType(dto: PatternDocumentDTO, type: FabricBaseType | 'none',
  catalog: ParameterCatalog | null): PatternDocumentDTO {
  const current = fabricBase(dto)
  if (type === 'none') return current ? changed(dto, null) : dto
  if (current?.type === type) return dto
  const group = groupFor(catalog, 'fabric_base', type)
  if (!group) throw new Error('Python 参数定义尚未提供 Fabric Base。')
  const base = Object.fromEntries(group.parameters.map((parameter) => [parameter.id, parameter.default])) as unknown as FabricBaseConfig
  base.type = type
  if (current) { base.thickness_mm = current.thickness_mm; base.margin_mm = current.margin_mm }
  validBase(base)
  return changed(dto, base)
}

export function updateFabricBase(dto: PatternDocumentDTO, key: string, value: ParameterValue,
  catalog: ParameterCatalog | null): PatternDocumentDTO {
  const current = fabricBase(dto)
  if (!current) throw new Error('请先选择 Fabric Base 类型。')
  const definition = groupFor(catalog, 'fabric_base', current.type)?.parameters.find((item) => item.id === key)
  if (!definition || !validateParameter(definition, value) || typeof value !== 'number') {
    throw new Error(`Fabric Base 参数 ${key} 无效。`)
  }
  if (current[key as keyof FabricBaseConfig] === value) return dto
  const next = { ...current, [key]: value }
  validBase(next)
  return changed(dto, next)
}
