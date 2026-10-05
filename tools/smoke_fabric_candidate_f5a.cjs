const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function commit(action){const response=page.waitForResponse(r=>r.url().endsWith('/evaluate')&&r.request().method()==='POST');await action();assert.equal((await response).status(),200);}
 async function check(){const response=page.waitForResponse(r=>r.url().endsWith('/fabric/candidate'));await page.getByRole('button',{name:'检查可制造性',exact:true}).click();const r=await response;assert.equal(r.status(),200,await r.text());await page.getByText('预检完成（未融合）',{exact:true}).waitFor();return r.json();}
 try{
  await page.goto(process.env.F5A_SMOKE_URL||'http://127.0.0.1:8773');
  await page.getByRole('banner').getByText('已连接',{exact:true}).waitFor();
  await commit(()=>page.getByRole('button',{name:'打开示例：基础圆点阵列'}).click());
  await page.getByRole('button',{name:'制造 Manufacture',exact:true}).click();
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('solid'));
  await commit(()=>page.getByLabel('Unit Cell 类型').selectOption('pyramid'));
  const solid=await check();assert.ok(solid.enabled_instance_count>0);assert.equal(solid.attachment_counts.ATTACHED,solid.enabled_instance_count);
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('grid'));
  await page.getByText('设计已变化，请重新检查可制造性。',{exact:true}).waitFor();
  const grid=await check();assert.ok(grid.attachment_counts.DETACHED>0);
  assert.equal(grid.export_available,false);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({solid:{count:solid.enabled_instance_count,counts:solid.attachment_counts,bounds:solid.bounds_mm},grid:{counts:grid.attachment_counts},errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
