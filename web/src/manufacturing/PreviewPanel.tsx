import type { ManufacturingBuildResult } from '../api/manufacturing'
import type { ManufacturingStatus } from './useManufacturing'
import { StlExportButton } from './StlExportButton'
import { ThreePreview } from './ThreePreview'
import type { PatternDocumentDTO } from '../model/types'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { FabricThreePreview } from './FabricThreePreview'
import { FABRIC_PREVIEW_NOTICE } from './fabricCopy'

interface Props {
  result: ManufacturingBuildResult | null
  status: ManufacturingStatus
  projectName: string | null
  isCurrentResult: (resultId: string) => boolean
  document?: PatternDocumentDTO | null
  fabricPreview?: FabricDesignPreview | null
}

export function PreviewPanel({ result, status, projectName, isCurrentResult, document, fabricPreview }: Props) {
  const isFabric = Boolean(document?.document.metadata.fabric_config)
  if (isFabric) return <section className="preview-panel" aria-label="Fabric 设计预览">
    <div className="preview-header"><div><span className="eyebrow">FABRIC DESIGN PREVIEW</span><h1>3D 设计预览</h1>
      <p>{FABRIC_PREVIEW_NOTICE}</p></div><button type="button" disabled>Fabric STL 尚未开放</button></div>
    {fabricPreview ? <FabricThreePreview key={fabricPreview.preview_id} plan={fabricPreview} />
      : <p>设计已变化或尚未预览。请返回 Fabric 页面点击「更新3D预览」。</p>}
  </section>
  if (!result) return <section className="preview-empty" aria-label="三维预览未就绪">
    <h1>3D 模型</h1>
    <p>{status === 'stale' ? '设计或厚度已变化，旧预览与 STL 已失效。请返回制造模式重新检查并生成。'
      : '请先在制造模式点击「检查并生成」，再查看最终模型和下载 STL。'}</p>
    <StlExportButton result={result} status={status} projectName={projectName}
      isCurrentResult={isCurrentResult} />
  </section>

  return <section className="preview-panel" aria-label="最终模型与导出">
    <div className="preview-header"><div><span className="eyebrow">VALIDATED MANUFACTURING RESULT</span><h1>3D 模型</h1>
      <p>XYZ：{result.bounds_mm?.size_x.toFixed(2)} × {result.bounds_mm?.size_y.toFixed(2)} × {result.bounds_mm?.size_z.toFixed(2)} mm
        {' · '}组件：{result.component_count}</p></div>
      <StlExportButton result={result} status={status} projectName={projectName}
        isCurrentResult={isCurrentResult} /></div>
    <ThreePreview key={result.manufacturing_result_id} resultId={result.manufacturing_result_id} />
    <small className="manufacturing-result-id">预览与 STL 共用结果编号：{result.manufacturing_result_id}</small>
  </section>
}
