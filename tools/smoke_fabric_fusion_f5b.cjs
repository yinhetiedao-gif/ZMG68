const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function commit(action){const wait=page.waitForResponse(r=>r.url().endsWith('/evaluate')&&r.request().method()==='POST');await action();assert.equal((await wait).status(),200);}
 async function fuse(expected){const wait=page.waitForResponse(r=>r.url().endsWith('/fabric/fusion'));await page.getByRole('button',{name:'生成最终制造网格',exact:true}).click();const r=await wait;assert.equal(r.status(),expected,await r.text());return r.json();}
 try{
  await page.goto(process.env.F5B_SMOKE_URL||'http://127.0.0.1:8773');
  await page.getByRole('banner').getByText('已连接',{exact:true}).waitFor();
  await commit(()=>page.getByRole('button',{name:'打开示例：基础圆点阵列'}).click());
  await page.getByRole('button',{name:'制造 Manufacture',exact:true}).click();
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('solid'));
  await commit(()=>page.getByLabel('Unit Cell 类型').selectOption('pyramid'));
  const solid=await fuse(200);
  await page.getByText('最终网格已通过检查',{exact:true}).waitFor();
  assert.equal(solid.connected_component_count,1);assert.equal(solid.validation_report.degenerate_face_count,0);
  assert.equal(solid.export_available,false);assert.equal(solid.interface_overlap_mm,0);
  assert.equal(await page.getByRole('button',{name:'Fabric STL 尚未开放',exact:true}).isDisabled(),true);
  const cached=await fuse(200);assert.equal(cached.cache_hit,true);
  assert.equal(cached.final_fabric_mesh_id,solid.final_fabric_mesh_id);
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('grid'));
  await page.getByText('设计已变化，请重新生成最终制造网格。',{exact:true}).waitFor();
  const grid=await fuse(422);assert.equal(grid.fusion_report.stage,'preflight');assert.ok(grid.fusion_report.failure_id);
  await page.getByRole('alert').filter({hasText:'失败编号'}).waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({solid,cached:cached.cache_hit,grid_stage:grid.fusion_report.stage,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
