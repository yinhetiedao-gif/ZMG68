import { describe, expect, it } from 'vitest'
import { clearDraft, loadBeforeExampleDraft, loadDraft, saveBeforeExampleDraft, saveDraft } from './localDraft'
import type { PatternDocumentDTO } from '../model/types'
import { Blob as NodeBlob } from 'node:buffer'

function project(): PatternDocumentDTO {
  return { schema_version: '1.0', document_id: 'draft-1', document_revision: 7, assets: [], document: {
    schema_version: 1, canvas: { width: 60, height: 60, unit: 'mm', mm_per_unit: 1 },
    reference: {}, elements: [{ id: 'circle-1', type: 'circle', x: 4, y: 5, width: 3, height: 3,
      rotation: 0, visible: true }], groups: [], transforms: {},
    metadata: { fabric_config: { base: { type: 'grid' } }, 'xiaomang_pattern_lab.parametric': { family: 'grid' } },
    fields: [{ id: 'wave-1', type: 'wave', parameters: { period: 12 } }],
    modifiers: [{ id: 'size-1', type: 'size', field_id: 'wave-1' }],
  } }
}

describe('last working draft', () => {
  it('round-trips the canonical DTO, mm, layout, fields, modifiers, fabric and original blob', async () => {
    const dto = project()
    const source = { blob: new NodeBlob(['<svg/>'], { type: 'image/svg+xml' }) as Blob,
      filename: 'circles.svg', media_type: 'image/svg+xml' }
    await saveDraft(dto, 'circles.svg', source)
    const restored = await loadDraft()
    expect(restored?.dto).toEqual(dto)
    expect(restored?.dto.document.canvas.mm_per_unit).toBe(1)
    expect(restored?.dto.document.fields).toHaveLength(1)
    expect(restored?.dto.document.modifiers).toHaveLength(1)
    expect(restored?.source_asset?.filename).toBe('circles.svg')
    expect(restored?.source_asset?.blob.size).toBeGreaterThan(0)
    await clearDraft()
    expect(await loadDraft()).toBeNull()
  })

  it('keeps only the newest draft and refuses an evaluate request above 2 MiB', async () => {
    const first = project()
    await saveDraft(first, 'first.svg', null)
    const second = { ...project(), document_id: 'draft-2', document_revision: 8 }
    await saveDraft(second, 'second.svg', null)
    expect((await loadDraft())?.dto.document_id).toBe('draft-2')
    const large = project()
    large.document.metadata.large = 'x'.repeat(2 * 1024 * 1024)
    await expect(saveDraft(large, 'large.svg', null)).rejects.toThrow(/2 MiB/)
    expect((await loadDraft())?.dto.document_id).toBe('draft-2')
  })

  it('keeps the pre-example work recoverable after the example becomes the newest draft', async () => {
    const original = project()
    await saveDraft(original, 'my-work.svg', null)
    await saveBeforeExampleDraft(original, 'my-work.svg', null)
    await saveDraft({ ...project(), document_id: 'example-current' }, '基础圆点阵列', null)
    expect((await loadDraft())?.dto.document_id).toBe('example-current')
    expect((await loadBeforeExampleDraft())?.dto).toEqual(original)
    await clearDraft()
    expect(await loadBeforeExampleDraft()).toBeNull()
  })
})
