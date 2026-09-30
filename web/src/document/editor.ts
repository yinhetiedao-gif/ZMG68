import type { PatternDocument, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'
import { groupFor, validateParameter, type ParameterCatalog } from './parameterSchema'
import {
  asRecord, ELEMENT_SPECS, FIELD_SPECS, GRID_SPECS, MAPPING_SPECS,
  PARAMETRIC_KEY, PLACEMENT_KEY, POSITION_SPECS, STACK_KEY,
} from './selectors'

export class DocumentEditError extends Error {}

function numeric(value: number, key: string, specs: { key: string; min: number; max: number; integer?: boolean }[]): number {
  const rule = specs.find((item) => item.key === key)
  if (!rule || !Number.isFinite(value) || value < rule.min || value > rule.max || (rule.integer && !Number.isInteger(value))) {
    throw new DocumentEditError(`参数 ${key} 超出当前可编辑范围。`)
  }
  if (key === 'direction' && value !== -1 && value !== 1) throw new DocumentEditError('方向只能为 -1 或 1。')
  return value
}

function catalogValue(catalog: ParameterCatalog | null, category: 'layout' | 'field' | 'modifier',
  type: string, key: string, value: number | boolean | string): boolean {
  const group = groupFor(catalog, category, type)
  if (!group) return false
  const definition = group.parameters.find((item) => item.id === key)
  if (!definition) throw new DocumentEditError(`参数 ${key} 不在 Python Schema 中。`)
  if (!validateParameter(definition, value)) throw new DocumentEditError(`参数 ${key} 超出 Python Schema 允许范围。`)
  return true
}

function changed(dto: PatternDocumentDTO, document: PatternDocument): PatternDocumentDTO {
  return { ...dto, document_revision: dto.document_revision + 1, document }
}

export function restoreSnapshot(snapshot: PatternDocumentDTO, currentRevision: number): PatternDocumentDTO {
  return { ...snapshot, document_revision: currentRevision + 1 }
}

export function updateElement(dto: PatternDocumentDTO, id: string, key: string, valueMm: number): PatternDocumentDTO {
  numeric(valueMm, key, ELEMENT_SPECS)
  const scale = millimetresPerUnit(dto.document)
  if (!scale) throw new DocumentEditError('项目缺少毫米映射。')
  const source = dto.document.elements.find((item) => item.id === id)
  if (!source) throw new DocumentEditError('源元素不存在。')
  const value = key === 'rotation' ? valueMm : valueMm / scale
  if (source[key] === value) return dto
  const next = { ...source, [key]: value }
  const transforms = { ...dto.document.transforms }
  if (transforms[id] && ['x', 'y', 'rotation'].includes(key)) transforms[id] = { ...transforms[id], [key]: value }
  return changed(dto, {
    ...dto.document,
    elements: dto.document.elements.map((item) => item.id === id ? next : item), transforms,
  })
}

export function updateField(dto: PatternDocumentDTO, id: string, key: string, value: number | boolean | string,
  catalog: ParameterCatalog | null = null): PatternDocumentDTO {
  let found = false
  const fields = dto.document.fields.map((field) => {
    if (field.id !== id) return field
    found = true
    const type = String(field.type)
    if (type === 'image' || type === 'composite' || (!FIELD_SPECS[type] && !groupFor(catalog, 'field', type))) throw new DocumentEditError('此参数场目前只读。')
    const parameters = asRecord(field.parameters) ?? {}
    if (key === 'invert') {
      if (typeof value !== 'boolean' || !('invert' in parameters)) throw new DocumentEditError('该场不支持反转。')
      catalogValue(catalog, 'field', type, key, value)
    } else {
      if (!(key in parameters)) throw new DocumentEditError('该参数不存在。')
      if (!catalogValue(catalog, 'field', type, key, value)) {
        if (typeof value !== 'number') throw new DocumentEditError('该参数需要数字。')
        numeric(value, key, FIELD_SPECS[type])
      }
      if (type === 'linear' && (key === 'start' || key === 'end')) {
        const start = key === 'start' ? value : parameters.start
        const end = key === 'end' ? value : parameters.end
        if (typeof start !== 'number' || typeof end !== 'number' || start >= end) throw new DocumentEditError('线性场终点必须大于起点。')
      }
    }
    // Python's SpiralField stores direction as ±1; its UI schema presents
    // these as two choices without changing the persisted numeric model.
    const stored = type === 'spiral' && key === 'direction' ? Number(value) : value
    return { ...field, parameters: { ...parameters, [key]: stored } }
  })
  if (!found) throw new DocumentEditError('参数场不存在。')
  if (fields.every((field, index) => field === dto.document.fields[index])) return dto
  return changed(dto, { ...dto.document, fields })
}

export function addField(dto: PatternDocumentDTO, type: string, catalog: ParameterCatalog | null): {
  dto: PatternDocumentDTO; id: string
} {
  const group = groupFor(catalog, 'field', type)
  if (!group || type === 'image' || type === 'composite') throw new DocumentEditError('此参数场暂不能从网页创建。')
  const parameters: Record<string, number | boolean> = {}
  for (const definition of group.parameters) {
    if (!validateParameter(definition, definition.default)) throw new DocumentEditError('Python 参数场默认值无效。')
    const value = definition.default
    parameters[definition.id] = type === 'spiral' && definition.id === 'direction'
      ? Number(value) : value as number | boolean
  }
  const existing = new Set(dto.document.fields.map((field) => String(field.id)))
  let index = 1
  while (existing.has(`field-${index}`)) index++
  const id = `field-${index}`
  return { id, dto: changed(dto, { ...dto.document,
    fields: [...dto.document.fields, { id, type, parameters, enabled: true }],
  }) }
}

export function setFieldEnabled(dto: PatternDocumentDTO, id: string, enabled: boolean): PatternDocumentDTO {
  const field = dto.document.fields.find((item) => item.id === id)
  if (!field) throw new DocumentEditError('参数场不存在。')
  if ((field.enabled !== false) === enabled) return dto
  return changed(dto, { ...dto.document, fields: dto.document.fields.map((item) =>
    item.id === id ? { ...item, enabled } : item) })
}

export function removeField(dto: PatternDocumentDTO, id: string): PatternDocumentDTO {
  if (!dto.document.fields.some((item) => item.id === id)) throw new DocumentEditError('参数场不存在。')
  if (dto.document.modifiers.some((item) => item.field_id === id))
    throw new DocumentEditError('该参数场仍被效果层引用，请先更换效果层的参数场。')
  if (dto.document.fields.some((item) => item.type === 'composite' &&
      Object.values(asRecord(item.parameters) ?? {}).some((value) => value === id)))
    throw new DocumentEditError('该参数场仍被组合场引用，不能删除。')
  return changed(dto, { ...dto.document, fields: dto.document.fields.filter((item) => item.id !== id) })
}

export function bindScalarModifierField(dto: PatternDocumentDTO, modifierId: string, fieldId: string): PatternDocumentDTO {
  if (!dto.document.fields.some((item) => item.id === fieldId)) throw new DocumentEditError('目标参数场不存在。')
  const modifier = dto.document.modifiers.find((item) => item.id === modifierId)
  if (!modifier || !['size', 'rotation'].includes(String(modifier.type)))
    throw new DocumentEditError('该效果层暂不支持参数场绑定。')
  if (modifier.field_id === fieldId) return dto
  return changed(dto, { ...dto.document, modifiers: dto.document.modifiers.map((item) =>
    item.id === modifierId ? { ...item, field_id: fieldId } : item) })
}

export function updateScalarModifier(dto: PatternDocumentDTO, id: string, key: string, value: number | boolean,
  catalog: ParameterCatalog | null = null): PatternDocumentDTO {
  let found = false
  const modifiers = dto.document.modifiers.map((modifier) => {
    if (modifier.id !== id) return modifier
    found = true
    const type = String(modifier.type)
    if (!['size', 'rotation', 'field_position', 'density'].includes(type)) throw new DocumentEditError('未知效果层只读。')
    if (key === 'enabled') {
      if (typeof value !== 'boolean') throw new DocumentEditError('启用状态无效。')
      return { ...modifier, enabled: value }
    }
    if (typeof value !== 'number') throw new DocumentEditError('效果参数需要数字。')
    if (type === 'density' && key === 'threshold') {
      numeric(value, key, [{ key: 'threshold', min: 0, max: 1 }])
      return { ...modifier, threshold: value }
    }
    if ((type === 'size' || type === 'rotation') && (MAPPING_SPECS.some((item) => item.key === key) ||
        groupFor(catalog, 'modifier', type)?.parameters.some((item) => item.id === key))) {
      if (!catalogValue(catalog, 'modifier', type, key, value)) numeric(value, key, MAPPING_SPECS)
      const mapping = asRecord(modifier.mapping) ?? {}
      if (type === 'size' && (key === 'min_output' || key === 'max_output') && value < 0) throw new DocumentEditError('尺寸比例不能为负。')
      return { ...modifier, mapping: { ...mapping, [key]: value } }
    }
    throw new DocumentEditError('该效果参数目前只读。')
  })
  if (!found) throw new DocumentEditError('效果层不存在。')
  return changed(dto, { ...dto.document, modifiers })
}

export function updateStackModifier(dto: PatternDocumentDTO, id: string, key: string, value: number | boolean): PatternDocumentDTO {
  const stack = asRecord(dto.document.metadata[STACK_KEY])
  if (!stack || !Array.isArray(stack.modifiers)) throw new DocumentEditError('有序效果堆栈不存在。')
  let found = false
  const modifiers = stack.modifiers.map((raw) => {
    const layer = asRecord(raw)
    if (!layer || layer.id !== id) return raw
    found = true
    if (!['size', 'rotation', 'position'].includes(String(layer.type))) throw new DocumentEditError('未知效果层只读。')
    if (key === 'enabled') {
      if (typeof value !== 'boolean') throw new DocumentEditError('启用状态无效。')
      return { ...layer, enabled: value }
    }
    if (layer.type !== 'position' || typeof value !== 'number') throw new DocumentEditError('该有序层目前只支持启用状态。')
    numeric(value, key, POSITION_SPECS)
    return { ...layer, parameters: { ...(asRecord(layer.parameters) ?? {}), [key]: value } }
  })
  if (!found) throw new DocumentEditError('有序效果层不存在。')
  return changed(dto, {
    ...dto.document,
    metadata: { ...dto.document.metadata, [STACK_KEY]: { ...stack, modifiers } },
  })
}

export function updateGrid(dto: PatternDocumentDTO, key: string, value: number,
  catalog: ParameterCatalog | null = null): PatternDocumentDTO {
  if (!catalogValue(catalog, 'layout', 'grid', key, value)) numeric(value, key, GRID_SPECS)
  const state = asRecord(dto.document.metadata[PARAMETRIC_KEY])
  if (state?.mode !== 'grid') throw new DocumentEditError('当前不是规则矩阵项目。')
  const base = asRecord(state.grid) ?? asRecord(state.model)
  if (!base || !(key in base)) throw new DocumentEditError('矩阵参数不存在。')
  const rows = key === 'rows' ? value : Number(base.rows)
  const columns = key === 'columns' ? value : Number(base.columns)
  if (rows * columns > 3000) throw new DocumentEditError('网页版暂时限制最多 3000 个矩阵单元。')
  const patch: Record<string, unknown> = { [key]: value }
  if (base.lock_aspect === true && key === 'element_width') patch.element_height = value
  if (base.lock_aspect === true && key === 'element_height') patch.element_width = value
  if (key === 'spacing_x' || key === 'spacing_y') {
    const vectorKey = key === 'spacing_x' ? 'basis_u_vector' : 'basis_v_vector'
    const vector = base[vectorKey]
    if (Array.isArray(vector) && vector.length === 2) {
      const length = Math.hypot(Number(vector[0]), Number(vector[1]))
      if (length <= 0) throw new DocumentEditError('矩阵基向量无效。')
      patch[vectorKey] = [Number(vector[0]) * value / length, Number(vector[1]) * value / length]
    }
  }
  if (key === 'rotation' && Array.isArray(base.basis_u_vector) && base.basis_u_vector.length === 2) {
    const u = base.basis_u_vector.map(Number)
    const currentAngle = Math.atan2(u[1], u[0]) * 180 / Math.PI
    const angle = (value - currentAngle) * Math.PI / 180
    const rotate = (vector: unknown) => Array.isArray(vector) && vector.length === 2
      ? [Number(vector[0]) * Math.cos(angle) - Number(vector[1]) * Math.sin(angle),
        Number(vector[0]) * Math.sin(angle) + Number(vector[1]) * Math.cos(angle)] : vector
    patch.basis_u_vector = rotate(base.basis_u_vector)
    patch.basis_v_vector = rotate(base.basis_v_vector)
  }
  const nextState = { ...state }
  for (const modelKey of ['grid', 'model', 'parametric_model']) {
    const model = asRecord(state[modelKey])
    if (model) nextState[modelKey] = { ...model, ...patch }
  }
  return changed(dto, { ...dto.document, metadata: { ...dto.document.metadata, [PARAMETRIC_KEY]: nextState } })
}

export function updateLayout(dto: PatternDocumentDTO, key: string, value: number | boolean,
  catalog: ParameterCatalog | null): PatternDocumentDTO {
  const state = asRecord(dto.document.metadata[PARAMETRIC_KEY])
  const mode = String(state?.mode ?? '')
  if (mode !== 'radial' && mode !== 'along_curve') throw new DocumentEditError('当前布局不支持此参数。')
  const model = asRecord(state?.model) ?? asRecord(state?.parametric_model)
  if (!model || !(key in model)) throw new DocumentEditError('布局参数不存在。')
  if (!catalogValue(catalog, 'layout', mode, key, value)) throw new DocumentEditError('缺少布局的 Python 参数定义。')
  if (model[key] === value) return dto
  const nextState = { ...state }
  for (const alias of ['model', 'parametric_model']) {
    const item = asRecord(state?.[alias])
    if (item) nextState[alias] = { ...item, [key]: value }
  }
  return changed(dto, { ...dto.document, metadata: { ...dto.document.metadata, [PARAMETRIC_KEY]: nextState } })
}

export function updateReplacement(dto: PatternDocumentDTO, elementId: string, prototypeId: string): PatternDocumentDTO {
  const state = asRecord(dto.document.metadata[PLACEMENT_KEY])
  if (state?.enabled !== true) throw new DocumentEditError('当前文档没有启用形状替换。')
  const prototypes = asRecord(state.shape_prototypes)
  if (prototypeId && !prototypes?.[prototypeId]) throw new DocumentEditError('形状原型不存在。')
  const replacement = { ...(asRecord(state.replacement_map) ?? {}) }
  if (prototypeId) replacement[elementId] = prototypeId
  else delete replacement[elementId]
  return changed(dto, {
    ...dto.document,
    metadata: { ...dto.document.metadata, [PLACEMENT_KEY]: { ...state, replacement_map: replacement } },
  })
}
