import type { ManufacturingBuildResult } from '../api/manufacturing'
import type { ManufacturingStatus } from './useManufacturing'
import { StlExportButton } from './StlExportButton'

interface Props {
  heightText: string
  onHeightChange: (value: string) => void
  validHeight: boolean
  canBuild: boolean
  onBuild: () => void
  status: ManufacturingStatus
  result: ManufacturingBuildResult | null
  error: string | null
  projectName: string | null
  isCurrentResult: (resultId: string) => boolean
  onPreview: () => void
}

const labels: Record<ManufacturingStatus, string> = {
  idle: '尚未生成', building: '正在检查并生成…', ready: '模型已生成',
  warning: '模型已生成，存在提醒', error: '生成失败', stale: '结果已过期，请重新检查并生成',
}

export function ManufacturingPanel(props: Props) {
  const { result, status } = props
  const geometry = result?.geometry_validation_summary
  const mesh = result?.mesh_validation_summary
  const conversion = result?.conversion_summary
  const notes = result ? [
    ...(result.component_count > 1 ? [`${result.component_count} 个独立组件；请确认每个组件都能独立打印。`] : []),
    ...result.warnings,
    ...(conversion?.warnings ?? []),
    ...(geometry?.issues ?? []).map((issue) => issue.message ?? issue.code ?? '二维几何问题'),
    ...(mesh?.issues ?? []).map((issue) => issue.message ?? issue.code ?? '网格问题'),
  ] : []
  return <section className="manufacturing-panel" aria-label="制造检查">
    <div className="manufacturing-heading"><span className="eyebrow">FINAL MANUFACTURING MESH</span><h1>制造检查</h1>
      <p>从当前二维设计生成最终制造网格；此操作不会更改设计或撤销历史。</p></div>
    <div className="manufacturing-settings">
      <label htmlFor="manufacturing-height">厚度 <span>mm</span></label>
      <input id="manufacturing-height" type="number" min="0.01" step="0.1" value={props.heightText}
        onChange={(event) => props.onHeightChange(event.target.value)} />
      <button type="button" onClick={props.onBuild} disabled={!props.canBuild || status === 'building'}>检查并生成</button>
    </div>
    {!props.validHeight && <p className="manufacturing-error" role="alert">厚度必须大于 0 mm。</p>}
    <div className={`manufacturing-status ${status}`} role="status">{labels[status]}</div>
    {props.error && <p className="manufacturing-error" role="alert">{props.error}</p>}
    {result && <div className="manufacturing-report">
      <small className="manufacturing-result-id">结果编号：{result.manufacturing_result_id}</small>
      <dl>
        <div><dt>几何检查</dt><dd>{geometry?.error_count ? `${geometry.error_count} 个错误` : `有效 · ${geometry?.checked_count ?? 0} 个元素`}</dd></div>
        <div><dt>连通性</dt><dd>{result.connectivity_summary.component_count} 个连通组件 · {result.connectivity_summary.isolated_count} 个孤立元素</dd></div>
        <div><dt>转换结果</dt><dd>{conversion?.converted_count ?? 0} / {conversion?.input_count ?? 0} 个元素转换 · 跳过 {conversion?.skipped_count ?? 0}</dd></div>
        <div><dt>Mesh 状态</dt><dd>{mesh?.is_watertight ? '封闭 · Watertight' : '未封闭'}{mesh ? ` · ${mesh.error_count} 个错误` : ''}</dd></div>
        <div><dt>独立组件</dt><dd>{result.component_count}</dd></div>
        <div><dt>XYZ 尺寸</dt><dd>{result.bounds_mm
          ? `${result.bounds_mm.size_x.toFixed(2)} × ${result.bounds_mm.size_y.toFixed(2)} × ${result.bounds_mm.size_z.toFixed(2)} mm`
          : '未取得尺寸'}</dd></div>
      </dl>
      {notes.length > 0 && <div className="manufacturing-notes"><strong>提醒 / 检查信息</strong><ul>{[...new Set(notes)].map((note) => <li key={note}>{note}</li>)}</ul></div>}
    </div>}
    <div className="manufacturing-output-actions">
      <button type="button" onClick={props.onPreview} disabled={!result || !props.isCurrentResult(result.manufacturing_result_id)}>3D 预览</button>
      <StlExportButton result={result} status={status} projectName={props.projectName} isCurrentResult={props.isCurrentResult} />
    </div>
  </section>
}
