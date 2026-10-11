import { describe, it, expect } from 'vitest'
import base from '../test/sizeFieldCatalog.json'
import design from '../test/designCatalog.json'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { designCandidate, designValues, gridValues, newInfluence, physicalGroup, validateInfluenceAreas } from './designControls'
import { openLinearSize, linearSizeCandidate, linearSizeOwner, resetLinearSizeDraft } from './linearSize'
import type { ParameterCatalog } from './parameterSchema'
import { restoreSnapshot } from './editor'
import { areaHandles, areaHandleChange } from '../geometry/influenceControls'
import { screenToWorld, worldToScreen } from '../geometry/view'
import { designSvg } from '../geometry/designExport'
import type { EvaluateResponse } from '../model/types'
import { saveDraft, loadDraft, clearDraft } from '../draft/localDraft'
import 'fake-indexeddb/auto'

const catalog = { ...base, definitions: { ...base.definitions, design } } as ParameterCatalog
describe('complete design panel connects one durable document and candidate', () => {
  it('public controls are source metadata, Grid stays authoritative; one commit/history', () => {
    const source = createExampleDocument('basic-grid', 'public'), json = JSON.stringify(source)
    let draft = { ...openLinearSize(source, phase1aBounds), controlsOnly: true, designValues: designValues(source, catalog), gridValues: gridValues(source)! }
    draft.designValues = { ...draft.designValues, size_percent: 150, aspect: 1.3, position_jitter: 2, seed: 18, stagger: true }
    draft.gridValues = { ...draft.gridValues, rows: 4, columns: 5, spacing_x: 10, spacing_y: 12 }
    const next = linearSizeCandidate(draft, catalog)
    expect(JSON.stringify(source)).toBe(json); expect(next.document_revision).toBe(source.document_revision)
    expect(next.document.fields).toEqual(source.document.fields); expect(next.document.modifiers).toEqual(source.document.modifiers)
    const applied = { ...next, document_revision: source.document_revision + 1 }
    expect(restoreSnapshot(source, applied.document_revision).document).toEqual(source.document)
    expect(restoreSnapshot(applied, applied.document_revision+1).document).toEqual(applied.document)
    expect(gridValues(next)?.rows).toBe(4)
    expect(() => designCandidate(source, catalog, { ...draft.designValues, aspect: 0 })).toThrow()
  })
  it('three consumer-local areas survive apply/reopen without duplicate Size or user field changes', () => {
    const source = createExampleDocument('basic-grid', 'areas'), draft = openLinearSize(source, phase1aBounds)
    draft.values.scope_mode = 'areas'; draft.values.invert = true
    draft.influenceAreas = []
    for (const type of ['line','ellipse','curve'] as const) draft.influenceAreas.push(newInfluence(type,phase1aBounds,catalog,draft.influenceAreas))
    const next = linearSizeCandidate(draft,catalog), opened=openLinearSize(JSON.parse(JSON.stringify(next)),phase1aBounds)
    expect(opened.influenceAreas).toEqual(draft.influenceAreas); expect(opened.values.invert).toBe(true)
    const repeated=linearSizeCandidate(opened,catalog)
    expect(repeated.document.modifiers).toHaveLength(1)
    expect(linearSizeOwner(repeated)?.modifier.id).toBe(linearSizeOwner(next)?.modifier.id)
    expect(() => newInfluence('line',phase1aBounds,catalog,draft.influenceAreas!)).toThrow()
  })
  it('artboard is independent, mm/cm/px representation never alters source; source conversion once', () => {
    const source=createExampleDocument('basic-grid','board'); source.document.canvas.mm_per_unit=.5
    const values=designValues(source,catalog); values.position_jitter=1
    const next=designCandidate(source,catalog,values,undefined,{width:80,height:50})
    expect(next.document.canvas.width).toBe(160); expect(next.document.canvas.height).toBe(100)
    expect(next.document.elements).toBe(source.document.elements)
    expect((next.document.metadata.web_design_controls as Record<string,unknown>).position_jitter).toBe(2)
    expect(physicalGroup(catalog.definitions.design!.random, .5)!.parameters.find(p=>p.id==='position_jitter')!.max).toBe(50)
    expect(() => designCandidate(source,catalog,values,undefined,{width:0,height:50})).toThrow()
  })
  it('invalid areas stop before candidate requests; Reset only changes the owned draft', () => {
    const source=createExampleDocument('basic-grid','reset'), json=JSON.stringify(source)
    const draft=openLinearSize(source,phase1aBounds), line=newInfluence('line',phase1aBounds,catalog,[])
    expect(() => validateInfluenceAreas([{...line,parameters:{...line.parameters,feather:line.parameters.width}}],1,catalog)).toThrow('半宽')
    const curve=newInfluence('curve',phase1aBounds,catalog,[])
    expect(() => validateInfluenceAreas([{...curve,parameters:{...curve.parameters,x2:curve.parameters.x0,y2:curve.parameters.y0}}],1,catalog)).toThrow('重合')
    expect(() => validateInfluenceAreas([{...line,parameters:{...line.parameters,x:NaN}}],1,catalog)).toThrow()
    draft.designValues={...designValues(source,catalog),size_percent:180,seed:71}
    draft.influenceAreas=[{...line,enabled:false}];draft.artboard={width:80,height:90}
    const reset=resetLinearSizeDraft(draft,catalog)
    expect(reset.designValues?.size_percent).toBe(100);expect(reset.artboard).toBeUndefined()
    expect(reset.influenceAreas?.[0].id).toBe(line.id);expect(reset.influenceAreas?.[0].enabled).toBe(true)
    expect(JSON.stringify(source)).toBe(json);expect(reset.source).toBe(source)
  })
  it('curve/ellipse/line handle coordinates use world space, not zoomed screen pixels', () => {
    for (const type of ['line','ellipse','curve'] as const) {
      const a=newInfluence(type,phase1aBounds,catalog,[]), h=areaHandles(a)
      const view={zoom:2.3,panX:74,panY:-51}, screen=worldToScreen(h.center,view)
      expect(screenToWorld(screen,view)).toEqual(h.center)
      const update=areaHandleChange(a,'center',{x:h.center.x+3,y:h.center.y+4},{x:3,y:4})
      expect(type==='curve'?update.x0:a.parameters.x+3).toBe(type==='curve'?a.parameters.x0+3:update.x)
    }
  })
  it('SVG is real current vector/path/holes with mm bounds; excludes auxiliary layers', () => {
    const dto=createExampleDocument('basic-grid','svg'); dto.document.canvas={width:120,height:80,origin_x:20,origin_y:40,unit:'px',mm_per_unit:.5}
    const result:EvaluateResponse={schema_version:'1.0',document_id:'svg',document_revision:dto.document_revision,bounds_mm:null,warnings:[],geometry:[
      {id:'hole',type:'filled_region',x:30,y:30,width:8,height:8,rotation:17,units:'mm',path_data:'M 0 0 L 10 0 L 10 10 L 0 10 Z M 3 3 L 3 7 L 7 7 L 7 3 Z',path_data_coordinate_system:'element_local',base_x:5,base_y:5,base_width:10,base_height:10,style:{'fill-rule':'evenodd'}},
    ]}
    const svg=designSvg(dto,result), xml=new DOMParser().parseFromString(svg,'image/svg+xml')
    expect(xml.documentElement.getAttribute('width')).toBe('60mm'); expect(xml.documentElement.getAttribute('viewBox')).toBe('10 20 60 40')
    expect(xml.querySelector('path')?.getAttribute('fill-rule')).toBe('evenodd')
    expect(xml.querySelector('image')).toBeNull(); expect(svg).not.toContain('gradient-controls'); expect(svg).not.toContain('design-grid')
    expect(() => designSvg(dto,{...result,document_revision:99})).toThrow()
  })
  it('applied controls/scopes and display preferences persist via existing IndexedDB, not pending form', async () => {
    await clearDraft()
    const dto=createExampleDocument('basic-grid','persist'), draft=openLinearSize(dto,phase1aBounds)
    draft.designValues={...designValues(dto,catalog),seed:42,size_random:.3};draft.values.scope_mode='areas'
    draft.influenceAreas=[newInfluence('curve',phase1aBounds,catalog,[])]
    const applied=linearSizeCandidate(draft,catalog)
    await saveDraft(applied,'test',null,{pending_layout:null,example_session_active:false,design_display:{unit:'cm',grid:true,pngWidth:1024}})
    const restored=await loadDraft()
    expect(restored?.dto).toEqual(applied);expect(restored?.design_display).toEqual({unit:'cm',grid:true,pngWidth:1024})
    expect(openLinearSize(restored!.dto,phase1aBounds).influenceAreas).toEqual(draft.influenceAreas)
    await clearDraft()
  })
})
