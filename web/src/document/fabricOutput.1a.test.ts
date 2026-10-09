import { describe, expect, it, vi } from 'vitest'
import { phase1aDocument, phase1aCatalog, phase1aBounds } from '../test/phase1aFixture'
import { fabricOutputMode, setFabricOutputMode, setFabricBaseType } from './fabricBase'
import { fabricUnitCell, setFabricUnitCellType, updateFabricUnitCell } from './fabricCell'
import { applyDirectionalFabricRecipe } from './fabricPresets'
import { restoreSnapshot } from './editor'
import { saveDraft, loadDraft } from '../draft/localDraft'
import { requestFabricFusion } from '../api/fabricFusion'

describe('1A explicit output mode and proportional size', () => {
  it('preserves old configurations; new configs default to cells only', () => {
    const old = phase1aDocument()
    expect(fabricOutputMode(old)).toBe('cells_with_base')
    const changed = setFabricOutputMode(old, 'cells_only')
    expect(changed.document_revision).toBe(old.document_revision + 1)
    expect(changed.document.elements).toBe(old.document.elements)
    expect(fabricOutputMode(restoreSnapshot(old, changed.document_revision))).toBe('cells_with_base')
    const fresh = structuredClone(old)
    delete fresh.document.metadata.fabric_config
    expect(fabricOutputMode(setFabricBaseType(fresh, 'solid', phase1aCatalog))).toBe('cells_only')
  })
  it('size scales width/depth once, preserves height/effects/placement and saved sizes', () => {
    const old = phase1aDocument()
    const config = old.document.metadata.fabric_config as any
    config.unit_cell.depth_mm = 1
    config.field_modifiers = { height: { enabled: true, field_id: 'test' } }
    const resized = updateFabricUnitCell(old, 'cell', 'uniform_size_mm', 4, phase1aCatalog)
    expect(fabricUnitCell(resized)).toMatchObject({ width_mm: 4, depth_mm: 2, height_mm: 3 })
    expect((resized.document.metadata.fabric_config as any).placement).toBe(config.placement)
    expect((resized.document.metadata.fabric_config as any).field_modifiers).toBe(config.field_modifiers)
    expect(setFabricUnitCellType(old, 'pyramid', phase1aCatalog)).toBe(old)
  })
  it('recipe v2 reset/undo/refresh includes output mode and larger actual dimensions', async () => {
    const old = phase1aDocument()
    const recipe = applyDirectionalFabricRecipe(old, phase1aCatalog, phase1aBounds)
    expect(fabricOutputMode(recipe)).toBe('cells_only')
    expect(fabricUnitCell(recipe)).toMatchObject({ width_mm: 4.8, depth_mm: 4.8, size_mode: 'follow_pattern' })
    expect(recipe.document.metadata.web_fabric_recipe).toMatchObject({ version: 2 })
    const changed = setFabricOutputMode(recipe, 'cells_with_base')
    expect(applyDirectionalFabricRecipe(changed, phase1aCatalog, phase1aBounds).document.metadata.fabric_config)
      .toEqual(recipe.document.metadata.fabric_config)
    await saveDraft(recipe, 'no-base', null)
    expect((await loadDraft())?.dto).toEqual(recipe)
    expect(restoreSnapshot(old, recipe.document_revision).document).toEqual(old.document)
  })
  it('only accepts multi-component final reports for the explicit cells-only mode', async () => {
    const dto = setFabricOutputMode(phase1aDocument(), 'cells_only')
    const report = { schema_version: '1.0', kind: 'final_fabric_mesh', document_id: dto.document_id,
      document_revision: dto.document_revision, final_fabric_mesh_id: 'test', output_mode: 'cells_only',
      final_fabric_mesh_ready: true, fused: false, export_available: false, connected_component_count: 9,
      watertight: true, volume_mm3: 40, interface_overlap_mm: 0, bounds_mm: [[10,20,0],[70,80,3]],
      validation_report: { is_watertight: true, finite_coordinates: true, error_count: 0, degenerate_face_count: 0, component_count: 9 } }
    const fetcher = (data: object) => vi.fn().mockResolvedValue(new Response(JSON.stringify(data)))
    expect((await requestFabricFusion(dto, undefined, fetcher(report))).connected_component_count).toBe(9)
    for (const bad of [{ ...report, output_mode: 'cells_with_base' }, { ...report, connected_component_count: 0 },
      { ...report, validation_report: { ...report.validation_report, degenerate_face_count: 1 } }])
      await expect(requestFabricFusion(dto, undefined, fetcher(bad))).rejects.toThrow('未通过')
  })
})
