import type { BoundsMM, PatternDocumentDTO } from '../model/types'
import { millimetresPerUnit } from '../model/project'
import { formatMm } from '../model/formatMm'

/** Informational only: applied authority bounds and the existing export rules. */
export function OutputDimensions({ document, bounds, pngWidth }: {
  document: PatternDocumentDTO; bounds: BoundsMM | null; pngWidth?: number
}) {
  const mm = millimetresPerUnit(document.document), c = document.document.canvas
  return <div className="inspector-readonly" aria-label="输出尺寸说明">
    <p>画板尺寸：{mm ? `${formatMm(c.width * mm)} × ${formatMm(c.height * mm)} mm` : '毫米映射未确认'}</p>
    <p>当前图案实际 XY：{bounds ? `X ${formatMm(bounds.min_x)}–${formatMm(bounds.max_x)}，Y ${formatMm(bounds.min_y)}–${formatMm(bounds.max_y)} mm（${formatMm(bounds.width)} × ${formatMm(bounds.height)} mm）` : '等待正式二维求值'}</p>
    {pngWidth !== undefined && <p>PNG：{pngWidth} × {Math.round(pngWidth * c.height / c.width)} px · 透明背景</p>}
    <p>SVG / PNG 按画板边界裁切；STL 使用实际制造几何，不按画板裁切。不含参考底图、网格或控制柄。</p>
  </div>
}
