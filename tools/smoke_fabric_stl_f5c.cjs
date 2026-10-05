const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const testing=process.env.F5C_EXPECT_TEST_EXPORT!=='0';
 const evidence=path.resolve('work/f5c-linkage-browser-'+Date.now());fs.mkdirSync(evidence,{recursive:true});
 async function commit(action){const wait=page.waitForResponse(r=>r.url().endsWith('/evaluate')&&r.request().method()==='POST');await action();assert.equal((await wait).status(),200);}
 try{
  await page.goto(process.env.F5C_SMOKE_URL||'http://127.0.0.1:8773');
  await page.getByRole('banner').getByText('已连接',{exact:true}).waitFor();
  await commit(()=>page.getByRole('button',{name:'打开示例：基础圆点阵列'}).click());
  await page.getByRole('button',{name:'制造 Manufacture',exact:true}).click();
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('solid'));
  await commit(()=>page.getByLabel('Unit Cell 类型').selectOption('pyramid'));
  for(const label of ['水平间距 (mm)','垂直间距 (mm)']) {
   const control=page.getByRole('region',{name:'Fabric Unit Cell',exact:true}).getByLabel(label,{exact:true});
   await control.fill('4');
   await commit(()=>control.press('Enter'));
  }
  await page.getByText('请先生成最终制造网格。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).isDisabled(),true);
  assert.equal(await page.getByText('最终制造网格生成失败。',{exact:true}).count(),0);
  const fused=page.waitForResponse(r=>r.url().endsWith('/fabric/fusion'));
  await page.getByRole('button',{name:'生成最终制造网格',exact:true}).click();
  const response=await fused;
  const trace={url:response.url(),status:response.status(),request:JSON.parse(response.request().postData()),body:await response.json()};
  fs.writeFileSync(path.join(evidence,'fusion.json'),JSON.stringify(trace,null,2));
  console.log(JSON.stringify({url:trace.url,status:trace.status,request_revision:trace.request.document_revision,
    response:trace.body}));
  assert.equal(response.status(),200,await response.text());
  const report=trace.body;assert.equal(report.export_available,testing);assert.equal(report.enabled_instance_count,100);
  if(!testing) {
   await page.getByText('网格已通过检查，当前环境未启用测试导出。',{exact:true}).waitFor();
   assert.equal(await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).isDisabled(),true);
   assert.equal(await page.getByText('最终制造网格生成失败。',{exact:true}).count(),0);
   await page.screenshot({path:path.join(evidence,'export-disabled.png'),fullPage:true});
   console.log(JSON.stringify({test_export_enabled:false,evidence,errors}));return;
  }
  await page.getByText('最终网格已通过检查',{exact:true}).waitFor();
  const downloaded=page.waitForEvent('download');
  const stlResponse=page.waitForResponse(r=>r.url().endsWith('/model.stl'));
  await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).click();
  const stl=await stlResponse;assert.equal(stl.status(),200);
  assert.deepEqual(JSON.parse(stl.request().postData()),trace.request);
  fs.writeFileSync(path.join(evidence,'stl-response.json'),JSON.stringify({url:stl.url(),status:stl.status(),
    headers:stl.headers(),document_revision:trace.request.document_revision,result_id:report.final_fabric_mesh_id},null,2));
  const download=await downloaded;assert.equal(download.suggestedFilename(),'xiaomang-fabric.stl');
  const output=path.join(evidence,'xiaomang-fabric.stl');await download.saveAs(output);
  const data=fs.readFileSync(output);assert.equal(data.length,84+50*data.readUInt32LE(80));
  await page.screenshot({path:path.join(evidence,'download-ready.png'),fullPage:true});
  await commit(()=>page.getByLabel('Fabric Base 类型').selectOption('grid'));
  await page.getByText('结果已失效，请重新生成。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).isDisabled(),true);
  const failed=page.waitForResponse(r=>r.url().endsWith('/fabric/fusion'));
  await page.getByRole('button',{name:'生成最终制造网格',exact:true}).click();
  const failure=await failed;assert.equal(failure.status(),422);
  const failureBody=await failure.json();fs.writeFileSync(path.join(evidence,'failed-fusion.json'),JSON.stringify(failureBody,null,2));
  await page.getByText('最终制造网格生成失败。',{exact:true}).waitFor();
  assert.ok((await page.getByRole('alert').allTextContents()).join(' ').includes(failureBody.fusion_report.failure_id));
  await page.screenshot({path:path.join(evidence,'validation-failed.png'),fullPage:true});
  assert.equal(await page.getByRole('button',{name:'下载测试 Fabric STL',exact:true}).isDisabled(),true);
  assert.deepEqual(errors,[]);console.log(JSON.stringify({file:output,bytes:data.length,triangles:data.readUInt32LE(80),errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
