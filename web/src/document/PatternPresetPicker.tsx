import { patternPresets, type PatternPresetId } from './patternPresets'
import precision from './patternPresetThumbnails/precision-stagger.svg'
import spectrum from './patternPresetThumbnails/spectrum-fade.svg'
import tide from './patternPresetThumbnails/diagonal-tide.svg'
import breath from './patternPresetThumbnails/local-breath.svg'
import coral from './patternPresetThumbnails/coral-grains.svg'
import ripple from './patternPresetThumbnails/ripple-center.svg'
const thumbnails = { 'precision-stagger': precision, 'spectrum-fade': spectrum, 'diagonal-tide': tide,
  'local-breath': breath, 'coral-grains': coral, 'ripple-center': ripple }

export function PatternPresetPicker({ onCreate, onApply, onEdit, currentId, createDisabled, applyDisabled }: {
  onCreate: (id: PatternPresetId) => void; onApply: (id: PatternPresetId) => void
  onEdit: (id: PatternPresetId) => void; currentId: PatternPresetId | null
  createDisabled: boolean; applyDisabled: boolean
}) {
  return <section className="pattern-preset-picker" aria-label="图案预设">
    <h3>图案预设</h3>
    <p className="inspector-readonly">创建新图案会先保存当前作品，并保留返回入口。应用效果只修改说明中的受管参数；仍可继续编辑。</p>
    {patternPresets.map(preset => <article key={preset.id} className="pattern-preset-card">
      <img src={thumbnails[preset.id]} alt={`${preset.title}默认求值结果`} width="120" height="120" />
      <div><h4>{preset.title}</h4><p>{preset.description}</p><small>{preset.scope}</small>
        <div className="pattern-preset-actions">
          <button type="button" disabled={createDisabled} onClick={() => onCreate(preset.id)}>创建{preset.title}</button>
          {preset.supportsCurrent && <button type="button" disabled={applyDisabled} onClick={() => onApply(preset.id)}>应用{preset.title}效果</button>}
          {currentId === preset.id && <button type="button" disabled={applyDisabled} onClick={() => onEdit(preset.id)}>编辑{preset.title}</button>}
        </div>
      </div>
    </article>)}
  </section>
}
