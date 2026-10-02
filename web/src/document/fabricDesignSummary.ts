import type { PatternDocumentDTO } from '../model/types'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { fabricBase } from './fabricBase'
import { fabricPlacement, fabricUnitCell } from './fabricCell'
import { fabricFieldModifier } from './fabricModifiers'

export function fabricDesignWarnings(dto: PatternDocumentDTO | null): string[] {
  const base = fabricBase(dto)
  const cell = fabricUnitCell(dto)
  const placement = fabricPlacement(dto)
  if (!base || !cell) return []
  const warnings: string[] = []
  const height = fabricFieldModifier(dto, 'height')
  const scale = fabricFieldModifier(dto, 'scale')
  const density = fabricFieldModifier(dto, 'density')
  const maxHeight = height?.enabled ? Number(height.max_height_mm) : cell.height_mm
  if (maxHeight / base.thickness_mm > 10) warnings.push('高度与基底厚度比例较大；打印稳定性需另行验证。')
  if (scale?.enabled && Number(scale.min_scale) < 0.3) warnings.push('最小比例过小，细节可能难以成型。')
  if (density?.enabled && Number(density.threshold) > 0.85) warnings.push('密度阈值较高，可见单元可能较少。')
  if ((placement?.mode ?? 'area_fill') === 'area_fill' && placement &&
    Math.min(placement.spacing_x_mm, placement.spacing_y_mm) < 1)
    warnings.push('布点间距较小，预览实例可能很多。')
  return warnings
}

export function fabricPreviewSummary(dto: PatternDocumentDTO | null, preview: FabricDesignPreview | null) {
  const cell = fabricUnitCell(dto)
  const placement = fabricPlacement(dto)
  const height = fabricFieldModifier(dto, 'height')
  const scale = fabricFieldModifier(dto, 'scale')
  const visible = preview?.instances.filter((item) => item.enabled) ?? []
  const range = (values: number[], unit = '') => {
    const low = Number(Math.min(...values).toFixed(2))
    const high = Number(Math.max(...values).toFixed(2))
    return `${low}${low === high ? '' : `–${high}`}${unit}`
  }
  return {
    cell: cell?.type ?? '无', instances: preview?.active_count ?? null,
    height: visible.length ? range(visible.map((item) => item.height_mm), ' mm')
      : cell ? height?.enabled ? `${height.min_height_mm}–${height.max_height_mm} mm` : `${cell.height_mm} mm` : '—',
    scale: visible.length ? range(visible.flatMap((item) => [item.scale * item.scale_x, item.scale * item.scale_y]))
      : scale?.enabled ? `${scale.min_scale}–${scale.max_scale}` : '1',
    placement: (placement?.mode ?? 'area_fill') === 'pattern_points' ? 'Pattern Points' : 'Area Fill',
    preview: preview ? preview.preview_simplified ? 'Simplified' : 'Full' : '待更新',
  }
}
