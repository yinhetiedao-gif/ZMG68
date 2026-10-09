import { ParameterPanel } from './ParameterPanel'
import { ParameterInteraction } from './ParameterInteraction'
import { referenceParameters, type ReferenceLayer } from './referenceLayer'
import type { ParameterValue } from './parameterSchema'

export function ReferenceLayerPanel({ layer, onCommit, onDraft, onRemove }: {
  layer: ReferenceLayer
  onCommit: (key: string, value: ParameterValue) => void
  onDraft: (key: string, value: ParameterValue | null) => void
  onRemove: () => void
}) {
  return <section className="inspector-section" aria-label="底图属性">
    <h3>参考底图</h3><p>{layer.filename}</p>
    <p className="inspector-readonly">仅用于二维参考；不计入图案、制造范围或 STL。缩放保持图片比例。</p>
    <ParameterInteraction.Provider value={{ syncToken: `${layer.filename}:${layer.width_mm}:${layer.x_mm}:${layer.y_mm}:${layer.opacity}:${layer.rotation_deg}` }}>
      <ParameterPanel group={referenceParameters} values={{ ...layer }} onCommit={onCommit} onDraft={onDraft} />
    </ParameterInteraction.Provider>
    <button type="button" onClick={onRemove}>移除参考底图</button>
  </section>
}
