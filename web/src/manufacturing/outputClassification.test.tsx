import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { ManufacturingPanel } from './ManufacturingPanel'
import { InspectorControls } from '../document/InspectorControls'
import { phase1aDocument, phase1aCatalog } from '../test/phase1aFixture'
import { unitCellChoices, setFabricUnitCellType, updateFabricUnitCell, fabricUnitCell } from '../document/fabricCell'
import type { ParameterCatalog } from '../document/parameterSchema'
const noop = () => undefined
function props(): ComponentProps<typeof ManufacturingPanel> {
 return {document:phase1aDocument(),parameterCatalog:phase1aCatalog,heightText:'2',onHeightChange:noop,validHeight:true,
  canBuild:true,onBuild:noop,status:'idle',result:null,error:null,projectName:'test',projectWarnings:[],isCurrentResult:()=>false,onPreview:noop,
  onFabricType:vi.fn(),onOutputMode:vi.fn(),onFabricParameter:noop,onUnitCellType:vi.fn(),onUnitCellParameter:noop,
  onPlacementMode:noop,onFabricModifierEnabled:noop,onFabricModifierField:noop,onFabricModifierParameter:noop,onFabricPreset:noop,
  fabricPreviewStatus:'idle',fabricPreviewResult:null,fabricPreviewError:null,onUpdateFabricPreview:noop,
 }
}
describe('output classification and element inspector states',()=>{
 it('moves only technical result details into the shared diagnostics while keeping stale, dimensions and warnings visible',()=>{
  render(<div data-testid="technical-host"/>);
  const p=props(),host=screen.getByTestId('technical-host');
  delete p.document!.document.metadata.fabric_config;
  p.onPreview=undefined;
  p.status='stale';p.previousResultRevision=2;
  p.result={schema_version:'1.0',manufacturing_result_id:'diagnostic-result',document_id:'phase1a',document_revision:2,status:'completed',
   geometry_validation_summary:{checked_count:9,error_count:0,warning_count:0,issues:[]},
   connectivity_summary:{component_count:9,isolated_count:9},
   conversion_summary:{input_count:9,converted_count:9,skipped_count:0,warnings:[]},
   mesh_validation_summary:{is_watertight:true,component_count:9,error_count:0,warning_count:0,issues:[]},
   bounds_mm:{size_x:40,size_y:40,size_z:2,units:'mm'},component_count:9,warnings:['测试安全提醒']};
  const ui=render(<ManufacturingPanel {...p} diagnosticsHost={host}/>);
  fireEvent.click(screen.getByRole('button',{name:'预览与最终制造'}));
  expect(within(host).getByText(/结果编号：diagnostic-result/)).toBeInTheDocument();
  expect(ui.container).not.toContainElement(within(host).getByRole('region',{name:'制造技术诊断'}));
  expect(screen.getByText(/上次结果 · 已失效/)).toBeVisible();
  expect(screen.getByText('40 × 40 × 2 mm')).toBeVisible();
  expect(screen.getByText('测试安全提醒')).toBeVisible();
  expect(screen.getByRole('button',{name:'导出 STL'})).toBeDisabled();
  expect(screen.queryByRole('button',{name:'3D 预览'})).toBeNull();
  expect(screen.queryByRole('button',{name:'返回设计'})).toBeNull();
 })
 it('retains standalone diagnostic access and explicit navigation callbacks without submitting manufacturing',()=>{
  const p=props();p.onBackDesign=vi.fn();p.onPreview=vi.fn();p.onBuild=vi.fn();
  render(<ManufacturingPanel {...p}/>);
  expect(screen.getByText('诊断详情').closest('details')).not.toHaveAttribute('open');
  fireEvent.click(screen.getByRole('button',{name:'返回设计'}));
  expect(p.onBackDesign).toHaveBeenCalledOnce();
  expect(p.onBuild).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'预览与最终制造'}));
  expect(screen.getByRole('button',{name:'3D 预览'})).toBeInTheDocument();
 })
 it('retains legacy base mode but hides base type for explicit cells-only, without implying contour output',()=>{
  const p=props(),ui=render(<ManufacturingPanel {...p}/>);
  expect(screen.getByLabelText('生成方式')).toHaveValue('cells');expect(screen.getByLabelText('单元输出')).toHaveValue('cells_with_base');
  expect(screen.getByLabelText('基底类型')).toHaveValue('solid');
  const next=structuredClone(p.document!);(next.document.metadata.fabric_config as Record<string,unknown>).output_mode='cells_only';
  ui.rerender(<ManufacturingPanel {...p} document={next}/>);
  expect(screen.queryByLabelText('基底类型')).toBeNull();expect(screen.getByLabelText('生成方式')).toHaveValue('cells');
  fireEvent.change(screen.getByLabelText('生成方式'),{target:{value:'contour'}});expect(p.onUnitCellType).toHaveBeenCalledWith('original');
  expect(p.onFabricType).not.toHaveBeenCalled();
  delete (next.document.metadata.fabric_config as Record<string,unknown>).unit_cell;
  ui.rerender(<ManufacturingPanel {...p} document={structuredClone(next)}/>);
  expect(screen.getByText(/旧无单元数据已保留/)).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'预览与最终制造'}));
  expect(screen.getByRole('button',{name:'生成最终制造网格'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'检查可制造性'})).toBeDisabled();expect(screen.getByRole('button',{name:'更新3D预览'})).toBeDisabled();
 })
 it('all six additions use the same immutable cell editor, schema bounds and preserved dimensions',()=>{
  const catalog=structuredClone(phase1aCatalog) as ParameterCatalog;
  for(const shape of unitCellChoices) catalog.definitions.fabric_cell![shape.type]={...catalog.definitions.fabric_cell!.pyramid,parameters:[
   ...catalog.definitions.fabric_cell!.pyramid.parameters,
   {id:'shape_ratio',label:'造型比例',type:'number',default:.5,value:.5,min:.1,max:.9,step:.01,unit:'',options:[]}]};
  let doc=phase1aDocument();const source=JSON.stringify(doc.document.elements);
  for(const type of ['dome','frustum','hex_prism','wedge','cross','ring'] as const){
   const old=doc;doc=setFabricUnitCellType(doc,type,catalog);expect(doc.document_revision).toBe(old.document_revision+1);
   expect(fabricUnitCell(doc)).toMatchObject({type,width_mm:2,depth_mm:2,height_mm:3});
   expect(JSON.stringify(doc.document.elements)).toBe(source);
   expect(()=>updateFabricUnitCell(doc,'cell','shape_ratio',0,catalog)).toThrow();
  }
 })
 it('unselected, single, multi and derived states do not expose misleading geometry edits',()=>{
  const dto=phase1aDocument(),common={dto,disabled:false,onEdit:noop,context:'element' as const};
  const ui=render(<InspectorControls {...common} selected={null}/>);expect(screen.getByText(/未选择对象/)).toBeVisible();
  const selected={id:'square',type:'rect' as const,x:40,y:50,width:60,height:60,rotation:0,units:'mm' as const};
  ui.rerender(<InspectorControls {...common} selected={selected}/>);expect(screen.getAllByRole('spinbutton').length).toBeGreaterThanOrEqual(5);
  ui.rerender(<InspectorControls {...common} selected={selected} selectionCount={2}/>);expect(screen.getByText(/已选择 2 个元素/)).toBeVisible();expect(screen.queryAllByRole('spinbutton')).toHaveLength(0);
  ui.rerender(<InspectorControls {...common} selected={{...selected,id:'derived'}}/>);expect(screen.getByText(/不可直接拖动/)).toBeVisible();expect(screen.queryAllByRole('spinbutton')).toHaveLength(0);
 })
})
