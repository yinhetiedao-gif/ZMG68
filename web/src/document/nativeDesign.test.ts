import { describe, expect, it } from 'vitest'
import { appendPrimitive, createBlankDesign } from './nativeDesign'
import { updateElement, restoreSnapshot } from './editor'
import { saveDraft, loadDraft, clearDraft } from '../draft/localDraft'
import { normalizeWorkspaceMode, workspaceModeFromLocation } from '../state/browserState'

describe('native 2D document entries and two workspaces', () => {
  it.each(['circle', 'ellipse', 'rect'] as const)('appends one editable %s in world units without replacing elements', async type => {
    const before = createBlankDesign('native'); before.document.canvas = { width: 120, height: 80, origin_x: 10, origin_y: -20, unit: 'px', mm_per_unit: .5 }
    const original = JSON.stringify(before)
    const first = appendPrimitive(before, type), second = appendPrimitive(first.dto, 'rect')
    expect(second.dto.document.elements).toHaveLength(2)
    expect(first.dto.document.elements[0]).toMatchObject({ x: 70, y: 20, width: 20, type })
    expect(JSON.stringify(before)).toBe(original)
    const edited = updateElement(second.dto, first.id, 'rotation', 45)
    expect(edited.document.elements[0].rotation).toBe(45)
    expect(restoreSnapshot(first.dto, edited.document_revision).document.elements).toHaveLength(1)
    await saveDraft(edited, 'native', null); expect((await loadDraft())?.dto).toEqual(edited); await clearDraft()
  })
  it('refuses silently replacing a generated layout or bypassing missing units', () => {
    const dto = createBlankDesign('native')
    dto.document.metadata['xiaomang_pattern_lab.parametric'] = { mode: 'grid' }
    expect(() => appendPrimitive(dto, 'circle')).toThrow(/不会自动替换/)
    delete dto.document.metadata['xiaomang_pattern_lab.parametric']
    dto.document.canvas.unit = 'px'; dto.document.canvas.mm_per_unit = null
    expect(() => appendPrimitive(dto, 'circle')).toThrow(/毫米映射/)
  })
  it('maps legacy preview links to manufacture and keeps invalid links safe', () => {
    expect(normalizeWorkspaceMode('preview')).toBe('manufacture')
    expect(normalizeWorkspaceMode('bogus')).toBe('design')
    window.history.replaceState(null, '', '/?mode=preview'); expect(workspaceModeFromLocation()).toBe('manufacture')
    window.history.replaceState(null, '', '/#preview'); expect(workspaceModeFromLocation()).toBe('manufacture')
    window.history.replaceState(null, '', '/')
  })
})
