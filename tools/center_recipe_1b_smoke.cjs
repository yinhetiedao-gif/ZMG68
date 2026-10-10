// Real production page + independent IndexedDB session, no user's draft mutation.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const origin=process.env.CENTER_SMOKE_ORIGIN||'http://127.0.0.1:8797';
const out=path.resolve('work/center-height-1b-20261010');fs.mkdirSync(out,{recursive:true});
const write=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2));
const source=JSON.parse(fs.readFileSync('web/src/examples/fixtures/basic-grid.pattern.json','utf8'));
source.canvas={width:120,height:80,origin_x:20,origin_y:40,unit:'svg',mm_per_unit:.5};
source.metadata={};source.elements=Array.from({length:100},(_,i)=>({id:'square-'+i,type:'rect',x:26+i%10*12,
 y:46+Math.floor(i/10)*8,width:6,height:4,rotation:i%3*10,visible:true,style:{},group_id:null,metadata:{},rx:0,ry:0}));
Object.assign(source.elements[44],{id:'hole',type:'filled_region',width:6,height:6,style:{fill:'black','fill-rule':'evenodd'},
 path_data:'M0 0H6V6H0Z M2 2H4V4H2Z',base_x:0,base_y:0,base_width:6,base_height:6,source_transform:''});
delete source.elements[44].rx;delete source.elements[44].ry;
source.transforms=Object.fromEntries(source.elements.map(e=>[e.id,{element_id:e.id,x:e.x,y:e.y,rotation:e.rotation,scale_x:1,scale_y:1}]));
const gradient=JSON.parse(fs.readFileSync('web/src/examples/fixtures/gradient-grid.pattern.json','utf8'));
source.fields=gradient.fields;source.modifiers=gradient.modifiers;
source.fields[0].parameters={angle:0,start:26,end:134};
Object.assign(source.modifiers[0].mapping,{min_output:.7,max_output:1});
Object.assign(source.modifiers[1].mapping,{min_output:-10,max_output:10});
const fixture={schema_version:'1.0',document_id:'center-browser-100',document_revision:0,document:source,assets:[]};
write('input-fixture.json',fixture);
const evidence={origin,requests:[],errors:[],cases:[],checks:{}};
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 const page=await context.newPage();page.setDefaultTimeout(30000);let current,plan;
 page.on('pageerror',e=>evidence.errors.push(e.message));
 page.on('response',async r=>{const p=new URL(r.url()).pathname,req=r.request();if(req.method()!=='POST')return;
  evidence.requests.push({path:p,status:r.status(),...(!r.ok()?{body:await r.text()}: {})});if(!r.ok())return;
  if(p.endsWith('/evaluate'))current={dto:req.postDataJSON().document,result:await r.json()};
  if(p.endsWith('/fabric/preview'))plan=await r.json();
 });
 const until=async check=>{for(let n=0;n<600;n++){if(check())return;await page.waitForTimeout(50);}throw Error('Latest authority did not arrive');};
 const ready=()=>page.getByLabel('编辑状态',{exact:true}).filter({hasText:'Ready'}).waitFor();
 const planReady=async()=>{await ready();await until(()=>plan?.document_id===current?.dto.document_id&&plan?.document_revision===current?.dto.document_revision);
  await page.locator('.three-preview-status').filter({hasText:'Fabric 设计预览已就绪'}).waitFor();};
 const heightField=()=>current.dto.document.fields.find(f=>f.id===current.dto.document.metadata.fabric_config.field_modifiers.height.field_id);
 const initialXY=()=>plan.instances.map(i=>[i.id,i.x_mm,i.y_mm,i.rotation_deg,i.cell_width_mm,i.cell_depth_mm]);
 const stableDesign=()=>{const cfg=current.dto.document.metadata.fabric_config;
  return {source:cfg.shape_source,cell:cfg.unit_cell,original:cfg.original_shape,base:cfg.base,output:cfg.output_mode,
   placement:cfg.placement,elements:current.dto.document.elements,modifiers:current.dto.document.modifiers,transforms:current.dto.document.transforms};};
 const verifyHeights=()=>{const p=heightField().parameters,h=current.dto.document.metadata.fabric_config.field_modifiers.height;
  assert.equal(heightField().type,'ring');assert.equal(p.radius,0);assert.equal(p.falloff,1);assert.equal(p.invert,false);
  for(const i of plan.instances){const value=Math.max(0,1-Math.hypot(i.x_mm-p.center_x,i.y_mm-p.center_y)/(p.ring_width/2));
   assert(Math.abs(i.height_mm-(h.min_height_mm+(h.max_height_mm-h.min_height_mm)*value))<1e-10);assert.equal(i.z_mm,0);}
 };
 const set=async(name,value)=>{const rev=current.dto.document_revision,n=evidence.requests.length,input=page.getByRole('spinbutton',{name,exact:true});
  // Focus first: the existing control exposes full precision on focus.
  // Filling before that render can append text to the newly restored value.
  await input.click();await input.fill(String(value));assert.equal(await input.inputValue(),String(value));
  assert.equal(current.dto.document_revision,rev);
  evidence.lastInput={name,value,beforeEnter:await input.inputValue(),disabled:await input.isDisabled()};
  await input.press('Enter');await page.waitForTimeout(100);
  evidence.lastInput.afterEnter=await input.inputValue();evidence.lastInput.alerts=await page.getByRole('alert').allTextContents();
  await until(()=>current.dto.document_revision===rev+1);await planReady();
  const requests=evidence.requests.slice(n);assert.equal(requests.filter(r=>r.path.endsWith('/evaluate')).length,1);
  assert.equal(requests.filter(r=>r.path.endsWith('/fabric/preview')).length,1);assert(requests.every(r=>!r.path.endsWith('/fusion')));
 };
 const recipe=async(id)=>{const rev=current.dto.document_revision,before=stableDesign(),n=evidence.requests.length;
  await page.getByLabel('Fabric 预设',{exact:true}).selectOption(id);await page.getByRole('button',{name:'应用预设',exact:true}).click();
  await until(()=>current.dto.document_revision===rev+1);await planReady();assert.deepEqual(stableDesign(),before);
  assert.equal(evidence.requests.slice(n).filter(r=>r.path.endsWith('/evaluate')).length,1);
  assert(evidence.requests.slice(n).every(r=>!r.path.endsWith('/fusion')));
 };
 const capture=async name=>{await planReady();assert.equal(await page.locator('canvas').count(),1);
  assert.equal(await page.getByText(/无法创建|WebGL 不可用/).count(),0);
  await page.getByRole('region',{name:'直接高度控制',exact:true}).scrollIntoViewIfNeeded();await page.waitForTimeout(500);
  await page.screenshot({path:path.join(out,name+'.png')});write(name+'-document.json',current.dto);write(name+'-preview.json',plan);
  evidence.cases.push({name,source:plan.shape_source,count:plan.count,field:heightField(),height:current.dto.document.metadata.fabric_config.field_modifiers.height,
   actualHeightRange:[Math.min(...plan.instances.map(i=>i.height_mm)),Math.max(...plan.instances.map(i=>i.height_mm))]});
 };
 const download=async name=>{const wait=page.waitForResponse(r=>r.url().endsWith('/fabric/fusion'));
  await page.getByRole('button',{name:'生成最终模型',exact:true}).click();const res=await wait;assert.equal(res.status(),200,await res.text());
  const final=await res.json();assert.equal(final.final_fabric_mesh_ready,true);await page.getByText(/最终网格已通过/).waitFor();
  const event=page.waitForEvent('download');await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).click();const file=await event;
  await file.saveAs(path.join(out,name+'.stl'));assert.equal(await file.failure(),null);write(name+'-final.json',final);
  evidence.checks[name+'Download']=true;
 };
 try{
  await page.goto(origin);await page.locator('.backend-badge.online').waitFor();
  evidence.scripts=await page.locator('script[src]').evaluateAll(nodes=>nodes.map(n=>n.src));
  evidence.health=await(await page.request.get(origin+'/api/v1/health')).json();
  await page.evaluate(async dto=>{const db=await new Promise(resolve=>{const r=indexedDB.open('xiaomang-pattern-lab-drafts',1);
   r.onupgradeneeded=()=>r.result.createObjectStore('drafts',{keyPath:'key'});r.onsuccess=()=>resolve(r.result);});
   await new Promise(resolve=>{const tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put({key:'last-working-draft',schema_version:'1.0',
    saved_at:new Date().toISOString(),dto,file_name:'Center height acceptance',source_asset:null,pending_layout:null,image_sources:{}});tx.oncomplete=resolve;});db.close();},fixture);
  await page.reload();await page.getByRole('button',{name:'恢复上次编辑',exact:true}).click();await ready();
  await page.getByRole('button',{name:/制造 Manufacture/}).click();await planReady();
  assert.equal(plan.count,100);assert.equal(plan.shape_source,'original');assert.equal(current.dto.document_revision,0);
  assert.equal(current.dto.document.metadata.fabric_config,undefined);
  const initial=initialXY(),n=evidence.requests.length;
  await page.getByLabel('Fabric 预设',{exact:true}).selectOption('center-height');
  await page.getByRole('button',{name:'应用预设',exact:true}).click();await until(()=>current.dto.document_revision===1);await planReady();
  assert.deepEqual(initialXY(),initial);assert.equal(plan.output_mode,'cells_only');assert.equal(plan.shape_source,'original');verifyHeights();
  const b=current.result.bounds_mm,p=heightField().parameters;
  assert(Math.abs(p.center_x-(b.min_x+b.max_x)/2)<1e-10);assert(Math.abs(p.center_y-(b.min_y+b.max_y)/2)<1e-10);
  assert(Math.abs(p.ring_width-Math.hypot(b.max_x-b.min_x,b.max_y-b.min_y))<1e-10);
  assert.equal(evidence.requests.slice(n).filter(r=>r.path.endsWith('/evaluate')).length,1);
  const defaultDoc=structuredClone(current.dto),defaultP=structuredClone(p);
  await capture('center-default-original');await download('center-default-original');
  await set('影响范围 (mm)',55);assert(await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).isDisabled());
  verifyHeights();assert.deepEqual(initialXY(),initial);await capture('center-broad-original');
  await set('影响范围 (mm)',11);verifyHeights();assert.deepEqual(initialXY(),initial);await capture('center-narrow-original');
  await set('中心 X (mm)',defaultP.center_x-14);await set('中心 Y (mm)',defaultP.center_y+6);await set('影响范围 (mm)',23);
  verifyHeights();assert.deepEqual(initialXY(),initial);await capture('center-offcenter-original');await download('center-offcenter-original');
  const edited=structuredClone(current.dto),rev=current.dto.document_revision;
  await page.getByRole('button',{name:'恢复中心隆起配方',exact:true}).click();await until(()=>current.dto.document_revision===rev+1);await planReady();
  assert.deepEqual(current.dto.document,defaultDoc.document);
  await page.getByRole('button',{name:'撤销',exact:true}).click();await planReady();assert.deepEqual(current.dto.document,edited.document);
  await page.getByRole('button',{name:'重做',exact:true}).click();await planReady();assert.deepEqual(current.dto.document,defaultDoc.document);
  const graph=structuredClone(stableDesign());
  for(const id of ['direction-gradient','wave-height','center-height','direction-gradient','center-height'])await recipe(id);
  assert.deepEqual(stableDesign(),graph);assert.equal(current.dto.document.fields.length,fixture.document.fields.length+3);
  verifyHeights();evidence.checks.originalSwitchingAndNoDuplicates=true;
  await page.locator('.project-unsaved').filter({hasText:'已保存'}).waitFor();const saved=structuredClone(current.dto);
  current=null;plan=null;await page.reload();await page.getByRole('button',{name:'恢复上次编辑',exact:true}).click();await ready();
  assert.deepEqual(current.dto,saved);assert(await page.getByRole('button',{name:'撤销',exact:true}).isDisabled());
  await page.getByRole('button',{name:/制造 Manufacture/}).click();await planReady();verifyHeights();
  assert.equal(await page.getByLabel('高度变化',{exact:true}).inputValue(),'center');assert.deepEqual(heightField().parameters,defaultP);
  evidence.checks.refreshCompleteGraphAndUndoBoundary=true;
  const revFin=current.dto.document_revision;
  await page.getByLabel('Unit Cell 类型',{exact:true}).selectOption('fin');await until(()=>current.dto.document_revision===revFin+1);await planReady();
  await page.getByRole('region',{name:'单元尺寸设置',exact:true}).getByText('高级：精确宽深与尺寸继承',{exact:true}).click();
  await set('单元宽度 (mm)',2);await set('单元深度 (mm)',1);
  await page.getByLabel('布点方式',{exact:true}).selectOption('pattern_points');await planReady();
  const finXY=initialXY(),finConfig=structuredClone(stableDesign());
  for(const id of ['direction-gradient','wave-height','center-height','direction-gradient','center-height'])await recipe(id);
  assert.deepEqual(stableDesign(),finConfig);assert.deepEqual(initialXY(),finXY);verifyHeights();
  assert(plan.instances.every(i=>i.cell_type==='fin'));assert.equal(plan.count,100);
  await capture('center-fin');await download('center-fin');
  evidence.checks={...evidence.checks,stableCentersAndWorldUnits:true,eachHeightSampled:true,resetUndoRedo:true,
   originalsHolesAnd2dPreserved:true,finSwitchingPreservesSourceAndOutput:true};
  assert.equal(evidence.errors.length,0);write('browser-evidence.json',evidence);
  console.log('PASS: center four original visual cases, real WebGL, three recipes/original+Fin, Reset/Undo/Redo/refresh, three Fabric downloads');
 }catch(error){write('browser-failure.json',{...evidence,current,plan,error:error.stack});await page.screenshot({path:path.join(out,'browser-failure.png')});throw error;}
 finally{await context.close();await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
