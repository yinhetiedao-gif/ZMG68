import { describe, it, expect } from 'vitest'
import { isOriginalShape, originalPreviewDocument, originalShape, setOriginalShape } from './fabricOriginal'
import { setFabricUnitCellType, fabricUnitCell } from './fabricCell'
import { applyOriginalHeightRecipe, applyWaveFabricRecipe } from './fabricPresets'
import { restoreSnapshot } from './editor'
import { phase1aCatalog as catalog, phase1aDocument, phase1aBounds } from '../test/phase1aFixture'
import { saveDraft, loadDraft } from '../draft/localDraft'

describe('explicit original source and legacy default original preview', () => {
  it('a separately explicit replacement recipe switches source while retaining the original profile', () => {
    const dto=setOriginalShape(phase1aDocument(),catalog,{size_scale:1.4,height_mm:4})
    const replaced=applyWaveFabricRecipe(dto,catalog)
    expect(isOriginalShape(replaced)).toBe(false)
    expect(fabricUnitCell(replaced)?.type).toBe('pyramid')
    expect(originalShape(replaced)).toEqual({size_scale:1.4,height_mm:4})
  })
  it('default original preview is a candidate, not a commit or a global reinterpretation of null cells', () => {
    const dto=phase1aDocument(); delete dto.document.metadata.fabric_config
    const before=JSON.stringify(dto), preview=originalPreviewDocument(dto,catalog,4)!
    expect(isOriginalShape(dto)).toBe(true)
    expect(preview.document_revision).toBe(dto.document_revision)
    expect(originalShape(preview)).toEqual({size_scale:1,height_mm:4})
    expect(JSON.stringify(dto)).toBe(before)
    const legacy=phase1aDocument();delete (legacy.document.metadata.fabric_config as any).unit_cell
    expect(isOriginalShape(legacy)).toBe(false)
    expect(originalPreviewDocument(legacy,catalog,2)).toBe(legacy)
  })
  it('original -> Fin -> original has one source and retains both parameter profiles and other bindings', () => {
    const c=structuredClone(catalog); c.definitions.fabric_cell!.fin=structuredClone(c.definitions.fabric_cell!.pyramid)
    const dto=phase1aDocument(), old=structuredClone(dto)
    let original=setOriginalShape(dto,c,{size_scale:1.5,height_mm:4})
    expect(fabricUnitCell(original)).toBeNull()
    const fin=setFabricUnitCellType(original,'fin',c)
    expect(fin.document_revision).toBe(original.document_revision+1)
    expect(fabricUnitCell(fin)?.type).toBe('fin')
    expect(originalShape(fin)).toEqual({size_scale:1.5,height_mm:4})
    original=setOriginalShape(fin,c)
    expect(originalShape(original)).toEqual({size_scale:1.5,height_mm:4})
    expect((original.document.metadata.fabric_config as any).unit_cell.type).toBe('fin')
    expect(restoreSnapshot(fin,original.document_revision).document).toEqual(fin.document)
    expect(dto).toEqual(old)
  })
  it.each(['wave','directional'] as const)('%s height application and Reset never replace original shape, placement or output', async kind=>{
    const dto=setOriginalShape(phase1aDocument(),catalog,{size_scale:1.4,height_mm:4})
    ;(dto.document.metadata.fabric_config as any).output_mode='cells_only'
    const initial=applyOriginalHeightRecipe(dto,catalog,phase1aBounds,kind,2)
    const before=dto.document.metadata.fabric_config as any, after=initial.document.metadata.fabric_config as any
    for(const key of ['unit_cell','original_shape','placement','base','output_mode'])expect(after[key]).toEqual(before[key])
    expect(initial.document_revision).toBe(dto.document_revision+1)
    expect(isOriginalShape(initial)).toBe(true)
    expect(fabricUnitCell(initial)).toBeNull()
    const reset=applyOriginalHeightRecipe(initial,catalog,phase1aBounds,kind,2)
    expect(reset.document).toEqual(initial.document)
    await saveDraft(reset,'original',null)
    expect((await loadDraft())?.dto).toEqual(reset)
  })
})
