import type { SourceAssetDraft } from '../draft/localDraft'
import type { PatternDocumentDTO } from '../model/types'
import type { ParameterGroup, ParameterValue } from './parameterSchema'
import { validateParameter } from './parameterSchema'
import { millimetresPerUnit } from '../model/project'

/** Display-only browser asset: never a field/reference input or manufacturing element. */
export interface ReferenceLayer extends SourceAssetDraft {
  x_mm: number; y_mm: number; width_mm: number; height_mm: number
  rotation_deg: number; opacity: number; visible: boolean; locked: boolean
}
export const referenceParameters: ParameterGroup = { label: '参考底图', parameters: [
  ...[['x_mm', '中心 X', 'mm', -10000, 10000, 0], ['y_mm', '中心 Y', 'mm', -10000, 10000, 0],
    ['width_mm', '底图宽度（等比缩放）', 'mm', .01, 10000, 60],
    ['rotation_deg', '底图旋转', '°', -360, 360, 0], ['opacity', '透明度', '', 0, 1, .35]].map(
      ([id, label, unit, min, max, value]) => ({ id: String(id), label: String(label), unit: String(unit),
        type: 'number' as const, min: Number(min), max: Number(max), default: Number(value), value: Number(value),
        step: id === 'opacity' ? .05 : .1, options: [],
        slider_min: id === 'opacity' ? 0 : id === 'width_mm' ? 1 : undefined,
        slider_max: id === 'opacity' ? 1 : id === 'width_mm' ? 300 : undefined })),
  ...[['visible', '显示底图', true], ['locked', '锁定底图', true]].map(([id, label, value]) => ({
    id: String(id), label: String(label), type: 'boolean' as const, default: Boolean(value), value: Boolean(value),
    min: null, max: null, step: null, unit: '', options: [] })),
] }
export function validateReferenceLayer(value: unknown): asserts value is ReferenceLayer {
  const layer = value as ReferenceLayer
  if (!layer || !layer.blob?.size || !Number.isFinite(layer.blob.size) || layer.blob.size > 8 * 1024 * 1024
    || typeof layer.blob.slice !== 'function' || layer.blob.type !== layer.media_type
    || !['image/png', 'image/jpeg'].includes(layer.media_type) || typeof layer.filename !== 'string'
    || !Number.isFinite(layer.height_mm) || layer.height_mm <= 0
    || referenceParameters.parameters.some(p => !validateParameter(p, layer[p.id as keyof ReferenceLayer] as ParameterValue)))
    throw new Error('参考底图数据无效，无法安全保存或恢复。')
}
export function updateReferenceLayer(layer: ReferenceLayer, key: string, value: ParameterValue): ReferenceLayer {
  const definition = referenceParameters.parameters.find(p => p.id === key)
  if (!definition || !validateParameter(definition, value)) throw new Error('底图参数超出合法范围。')
  const next = { ...layer, [key]: value,
    ...(key === 'width_mm' ? { height_mm: Number(value) * layer.height_mm / layer.width_mm } : {}) }
  validateReferenceLayer(next); return next
}
export async function readReferenceLayer(file: File, dto: PatternDocumentDTO): Promise<ReferenceLayer> {
  if (!['image/png', 'image/jpeg'].includes(file.type) || !file.size || file.size > 8 * 1024 * 1024)
    throw new Error('参考底图请使用不超过 8 MiB 的 PNG/JPG；不会转换为图案或参数场。')
  const image = await createImageBitmap(file)
  try {
    const s = millimetresPerUnit(dto.document)
    if (!s || !image.width || !image.height) throw new Error('无法读取底图尺寸或项目毫米映射。')
    const c = dto.document.canvas, width = Math.min(c.width * s, c.height * s * image.width / image.height)
    const layer: ReferenceLayer = { blob: file, filename: file.name, media_type: file.type,
      x_mm: ((c.origin_x ?? 0) + c.width / 2) * s, y_mm: ((c.origin_y ?? 0) + c.height / 2) * s,
      width_mm: width, height_mm: width * image.height / image.width,
      rotation_deg: 0, opacity: .35, visible: true, locked: true }
    validateReferenceLayer(layer); return layer
  } finally { image.close() }
}
