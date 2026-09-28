import type { PatternDocumentDTO } from '../model/types'

export const PARAMETRIC_KEY = 'xiaomang_pattern_lab.parametric'
export const STACK_KEY = 'xiaomang_pattern_lab.shared_modifiers'
export const PLACEMENT_KEY = 'xiaomang_pattern_lab.placement_assignment'

export interface NumericSpec { key: string; label: string; min: number; max: number; step: number; integer?: boolean }

const spec = (key: string, label: string, min: number, max: number, step = 0.1, integer = false): NumericSpec =>
  ({ key, label, min, max, step, integer })

// This is UI metadata for fields already parsed by the Python SharedFieldEngine.
// It never evaluates a field or creates a new field type.
export const FIELD_SPECS: Record<string, NumericSpec[]> = {
  constant: [spec('value', '固定值', 0, 1, 0.01)],
  linear: [spec('angle', '方向角度', -360, 360, 1), spec('start', '起点', -10000, 10000), spec('end', '终点', -10000, 10000)],
  ring: [spec('center_x', '中心 X', -10000, 10000), spec('center_y', '中心 Y', -10000, 10000), spec('radius', '半径', 0, 10000), spec('ring_width', '环宽', 0.01, 10000), spec('falloff', '衰减', 0.01, 20)],
  wave: [spec('angle', '角度', -360, 360, 1), spec('wavelength', '波长', 0.01, 10000), spec('phase', '相位', -100, 100), spec('amplitude', '振幅', 0, 1, 0.01), spec('offset', '基线', 0, 1, 0.01)],
  stripe: [spec('angle', '角度', -360, 360, 1), spec('period', '周期', 0.01, 10000), spec('phase', '相位', -100, 100), spec('duty_cycle', '占空比', 0, 1, 0.01), spec('smoothness', '柔化', 0, 0.5, 0.01)],
  checker: [spec('cell_width', '格宽', 0.01, 10000), spec('cell_height', '格高', 0.01, 10000), spec('angle', '角度', -360, 360, 1), spec('offset_x', '偏移 X', -10000, 10000), spec('offset_y', '偏移 Y', -10000, 10000)],
  spiral: [spec('center_x', '中心 X', -10000, 10000), spec('center_y', '中心 Y', -10000, 10000), spec('turns', '圈数', 0, 100), spec('phase', '相位', -100, 100), spec('direction', '方向 ±1', -1, 1, 2, true), spec('falloff', '衰减', 0.01, 20)],
  noise: [spec('scale', '尺度', 0.01, 10000), spec('strength', '强度', 0, 1, 0.01), spec('seed', '种子', -1000000000, 1000000000, 1, true), spec('offset_x', '偏移 X', -10000, 10000), spec('offset_y', '偏移 Y', -10000, 10000), spec('octaves', '层数', 1, 8, 1, true), spec('contrast', '对比度', 0.01, 20)],
}

export const GRID_SPECS = [
  spec('rows', '行数', 1, 500, 1, true), spec('columns', '列数', 1, 500, 1, true),
  spec('spacing_x', '水平间距 mm', 0.01, 10000), spec('spacing_y', '垂直间距 mm', 0.01, 10000),
  spec('element_width', '单元宽度 mm', 0.01, 10000), spec('element_height', '单元高度 mm', 0.01, 10000),
  spec('rotation', '整体旋转 °', -360, 360, 1),
  spec('offset_x', '原点 X mm', -10000, 10000), spec('offset_y', '原点 Y mm', -10000, 10000),
]

export const MAPPING_SPECS = [
  spec('min_output', '最小输出', -10000, 10000), spec('max_output', '最大输出', -10000, 10000),
  spec('strength', '作用强度', 0, 1, 0.01), spec('falloff', '衰减', 0.01, 20),
]

export const POSITION_SPECS = [
  spec('offset_x', '偏移 X mm', -10000, 10000), spec('offset_y', '偏移 Y mm', -10000, 10000),
  spec('center_x', '中心 X mm', -10000, 10000), spec('center_y', '中心 Y mm', -10000, 10000),
  spec('amount', '位移量 mm', -10000, 10000), spec('radius', '作用半径 mm', 0.01, 10000),
  spec('angle', '角度 °', -360, 360, 1), spec('wavelength', '波长 mm', 0.01, 10000),
  spec('phase', '相位', -100, 100), spec('strength', '强度', 0, 1, 0.01),
  spec('falloff', '衰减', 0.01, 20),
]

export const ELEMENT_SPECS = [
  spec('x', '位置 X mm', -10000, 10000), spec('y', '位置 Y mm', -10000, 10000),
  spec('width', '宽度 mm', 0.01, 10000), spec('height', '高度 mm', 0.01, 10000),
  spec('rotation', '旋转 °', -360, 360, 1),
]

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

export function fieldRecords(dto: PatternDocumentDTO): Record<string, unknown>[] {
  return dto.document.fields.filter((value) => asRecord(value))
}

export function scalarModifiers(dto: PatternDocumentDTO): Record<string, unknown>[] {
  return dto.document.modifiers.filter((value) => asRecord(value))
}

export function stackModifiers(dto: PatternDocumentDTO): Record<string, unknown>[] {
  const stack = asRecord(dto.document.metadata[STACK_KEY])
  return Array.isArray(stack?.modifiers) ? stack.modifiers.filter((value) => asRecord(value)) : []
}

export function gridModel(dto: PatternDocumentDTO): Record<string, unknown> | null {
  const state = asRecord(dto.document.metadata[PARAMETRIC_KEY])
  if (state?.mode !== 'grid') return null
  return asRecord(state.grid) ?? asRecord(state.model)
}

export function placementState(dto: PatternDocumentDTO): Record<string, unknown> | null {
  const state = asRecord(dto.document.metadata[PLACEMENT_KEY])
  return state?.enabled === true ? state : null
}
