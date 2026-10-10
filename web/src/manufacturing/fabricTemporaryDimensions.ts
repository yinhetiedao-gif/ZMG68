import type { PatternDocumentDTO } from '../model/types'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { fabricUnitCell } from '../document/fabricCell'
import { fabricFieldModifier } from '../document/fabricModifiers'
import { isOriginalShape, originalShape } from '../document/fabricOriginal'

/** Display only. Preserve authoritative XY/rotation/enabled and relative scales.
 * Python recalibrates after the one document commit; this plan is never sent to manufacturing. */
export function temporaryFabricDimensions(plan: FabricDesignPreview | null,
  accepted: PatternDocumentDTO | null, current: PatternDocumentDTO | null,
  draft: Record<string, number>): FabricDesignPreview | null {
  if (!plan || !accepted || !current || accepted.document_id !== current.document_id) return plan
  if (isOriginalShape(accepted) && isOriginalShape(current)) {
    const before = originalShape(accepted), next = originalShape(current) ?? before
    if (!before || !next) return plan
    const size = draft.original_size_scale ?? next.size_scale
    const height = draft.height_mm ?? next.height_mm
    if (![size, height].every(v => Number.isFinite(v) && v > 0)) return plan
    const xy = size / before.size_scale
    const z = !fabricFieldModifier(accepted, 'height')?.enabled && !fabricFieldModifier(current, 'height')?.enabled ? height / before.height_mm : 1
    return xy === 1 && z === 1 ? plan : { ...plan, instances: plan.instances.map(i => ({ ...i,
      cell_width_mm: i.cell_width_mm * xy, cell_depth_mm: i.cell_depth_mm * xy,
      height_mm: i.height_mm * z, cell_height_mm: i.cell_height_mm * z })) }
  }
  const before = fabricUnitCell(accepted), next = fabricUnitCell(current)
  if (!before || !next || before.type !== next.type) return plan
  const width = draft.uniform_size_mm ?? next.width_mm
  const depth = draft.uniform_size_mm === undefined ? next.depth_mm : width * next.depth_mm / next.width_mm
  const height = draft.height_mm ?? next.height_mm
  if (![width, depth, height].every(value => Number.isFinite(value) && value > 0)) return plan
  const x = width / before.width_mm, y = depth / before.depth_mm
  const uniform = !fabricFieldModifier(accepted, 'height')?.enabled && !fabricFieldModifier(current, 'height')?.enabled
  const z = uniform ? height / before.height_mm : 1
  if (x === 1 && y === 1 && z === 1) return plan
  return { ...plan, instances: plan.instances.map(item => ({ ...item,
    cell_width_mm: item.cell_width_mm * x, cell_depth_mm: item.cell_depth_mm * y,
    height_mm: item.height_mm * z, cell_height_mm: item.cell_height_mm * z })) }
}
