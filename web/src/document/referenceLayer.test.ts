import { describe, expect, it, vi } from 'vitest'
import { Blob as NodeBlob } from 'node:buffer'
import { createBlankDesign } from './nativeDesign'
import { readReferenceLayer, updateReferenceLayer, validateReferenceLayer, type ReferenceLayer } from './referenceLayer'
import { saveDraft, loadDraft, saveBeforeExampleDraft, loadBeforeExampleDraft } from '../draft/localDraft'

describe('display-only reference layer in existing draft storage', () => {
  const layer = (): ReferenceLayer => ({ blob: new NodeBlob(['png'], { type: 'image/png' }) as Blob,
    filename: 'guide.png', media_type: 'image/png', x_mm: 25, y_mm: -10, width_mm: 60, height_mm: 30,
    rotation_deg: 30, opacity: .35, visible: true, locked: true })
  it('preserves aspect, units, document/revision and Blob through draft/example protection', async () => {
    const dto = createBlankDesign('guide'), snapshot = JSON.stringify(dto)
    const guide = updateReferenceLayer(layer(), 'width_mm', 120)
    expect(guide.height_mm).toBe(60)
    const ui = { pending_layout: null, example_session_active: false, reference_layer: guide }
    await saveDraft(dto, 'guide', null, ui); await saveBeforeExampleDraft(dto, 'guide', null, ui)
    expect((await loadDraft())?.reference_layer).toMatchObject({ width_mm: 120, height_mm: 60, locked: true })
    expect((await loadBeforeExampleDraft())?.reference_layer?.blob.size).toBe(3)
    expect(JSON.stringify(dto)).toBe(snapshot)
    expect(dto.document.elements).toHaveLength(0); expect(dto.assets).toHaveLength(0)
  })
  it('rejects corrupt/unsupported data and does not overwrite a valid saved work', async () => {
    const dto = createBlankDesign('guide')
    await saveDraft(dto, 'valid', null)
    expect(() => validateReferenceLayer({ ...layer(), opacity: NaN })).toThrow(/无效/)
    expect(() => validateReferenceLayer({ ...layer(), blob: { size: 3, type: 'image/png' } })).toThrow(/无效/)
    expect(() => updateReferenceLayer(layer(), 'width_mm', 0)).toThrow(/合法/)
    await expect(saveDraft(dto, 'bad', null, { pending_layout: null, example_session_active: false,
      reference_layer: { ...layer(), media_type: 'image/svg+xml' } })).rejects.toThrow(/无效/)
    expect((await loadDraft())?.file_name).toBe('valid')
  })
  it('places decoded PNG/JPG in the same nonzero-origin, nonunit-mm world as geometry', async () => {
    const close = vi.fn(); vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ width: 400, height: 200, close }))
    const dto = createBlankDesign('guide'); dto.document.canvas = { width: 120, height: 80, origin_x: 10, origin_y: -20, unit: 'px', mm_per_unit: .5 }
    const file = new File(['image'], 'guide.png', { type: 'image/png' })
    expect(await readReferenceLayer(file, dto)).toMatchObject({ x_mm: 35, y_mm: 10, width_mm: 60, height_mm: 30, locked: true })
    expect(close).toHaveBeenCalledOnce()
    await expect(readReferenceLayer(new File(['svg'], 'x.svg', { type: 'image/svg+xml' }), dto)).rejects.toThrow(/PNG\/JPG/)
  })
})
