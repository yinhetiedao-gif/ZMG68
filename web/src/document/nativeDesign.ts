import type { PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit, prepareProject } from '../model/project'
import { currentLayoutFamily } from './layoutDraft'

export type PrimitiveType = 'circle' | 'ellipse' | 'rect'
export function createBlankDesign(id: string): PatternDocumentDTO {
  return prepareProject(JSON.stringify({ schema_version: 1,
    canvas: { width: 120, height: 80, unit: 'mm', mm_per_unit: 1, origin_x: 0, origin_y: 0 },
    reference: { source_path: '', visible: false, preprocessing: {}, metadata: {} }, elements: [], groups: [], transforms: {},
    metadata: {}, fields: [], modifiers: [] }), id).dto
}

/** Add one native Foundation element, never generate/bake/replace an array. */
export function appendPrimitive(dto: PatternDocumentDTO, type: PrimitiveType): { dto: PatternDocumentDTO; id: string } {
  if (!['circle', 'ellipse', 'rect'].includes(type)) throw new Error('此基础图形尚未接入。')
  if (currentLayoutFamily(dto) !== 'free' || dto.document.metadata['xiaomang_pattern_lab.parametric'])
    throw new Error('当前图案由布局或效果生成。请先明确应用自由布局，烘焙为可编辑元素后再添加独立图形；不会自动替换当前图案。')
  if (dto.document.metadata['xiaomang_pattern_lab.placement_assignment'] || dto.document.metadata['xiaomang_pattern_lab.shared_modifiers']
    || dto.document.fields.length || dto.document.modifiers.length)
    throw new Error('当前作品含共享场/效果或形状分配，现有引擎不能保证追加图形继续可直接编辑。本轮保留作品，不自动清除效果或替换源数据。')
  const scale = millimetresPerUnit(dto.document)
  if (!scale) throw new Error('当前项目缺少有效毫米映射。')
  const used = new Set(dto.document.elements.map(e => e.id)); let number = 1
  while (used.has(`native-${number}`)) number++
  const id = `native-${number}`, canvas = dto.document.canvas
  const element = { id, type, x: (canvas.origin_x ?? 0) + canvas.width / 2,
    y: (canvas.origin_y ?? 0) + canvas.height / 2, width: 10 / scale,
    height: (type === 'ellipse' ? 6 : 10) / scale, rotation: 0, visible: true, style: { fill: '#17201f' },
    group_id: null, metadata: {}, ...(type === 'rect' ? { rx: 0, ry: 0 } : {}) }
  return { id, dto: { ...dto, document_revision: dto.document_revision + 1,
    document: { ...dto.document, elements: [...dto.document.elements, element], transforms: { ...dto.document.transforms,
      [id]: { element_id: id, x: element.x, y: element.y, rotation: 0, scale_x: 1, scale_y: 1 } } } } }
}
