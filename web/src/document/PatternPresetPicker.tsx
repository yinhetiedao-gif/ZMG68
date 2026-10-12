import { patternPresets, type PatternPresetId } from './patternPresets'
import precision from './patternPresetThumbnails/precision-stagger.svg'
import spectrum from './patternPresetThumbnails/spectrum-fade.svg'
import tide from './patternPresetThumbnails/diagonal-tide.svg'
import breath from './patternPresetThumbnails/local-breath.svg'
import coral from './patternPresetThumbnails/coral-grains.svg'
import ripple from './patternPresetThumbnails/ripple-center.svg'
import weave from './patternPresetThumbnails/digital-weave.svg'
import vortex from './patternPresetThumbnails/vortex-scales.svg'
const thumbnails = { 'precision-stagger': precision, 'spectrum-fade': spectrum, 'diagonal-tide': tide,
  'local-breath': breath, 'coral-grains': coral, 'ripple-center': ripple, 'digital-weave': weave, 'vortex-scales': vortex }

export function PatternPresetPicker({ onCreate, onApply, onEdit, currentId, createDisabled, applyDisabled }: {
  onCreate: (id: PatternPresetId) => void; onApply: (id: PatternPresetId) => void
  onEdit: (id: PatternPresetId) => void; currentId: PatternPresetId | null
  createDisabled: boolean; applyDisabled: boolean
}) {
  return <section className="pattern-preset-picker" aria-label="图案预设">
    <h3>图案预设</h3>
    <details className="parameter-help"><summary>创建与应用说明</summary><p className="inspector-readonly">创建新图案会先保存当前作品，并保留返回入口。应用效果只修改说明中的受管参数；仍可继续编辑。</p></details>
    {patternPresets.map(preset => <article key={preset.id} className="pattern-preset-card">
      <img src={thumbnails[preset.id]} alt={`${preset.title}默认求值结果`} width="92" height="92" />
      <div className="pattern-preset-copy"><h4>{preset.title}</h4><p>{preset.description}</p><details className="parameter-help"><summary>作用范围</summary><small>{preset.scope}</small></details></div>
        <div className="pattern-preset-actions">
          <button type="button" disabled={createDisabled} onClick={() => onCreate(preset.id)}>创建{preset.title}</button>
          {preset.supportsCurrent && <button type="button" disabled={applyDisabled} onClick={() => onApply(preset.id)}>应用{preset.title}效果</button>}
          {currentId === preset.id && <button type="button" disabled={applyDisabled} onClick={() => onEdit(preset.id)}>编辑{preset.title}</button>}
        </div>
    </article>)}
  </section>
}
