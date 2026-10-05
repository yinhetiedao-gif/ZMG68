const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const out=path.resolve(__dirname,'../work/f4c');fs.mkdirSync(out,{recursive:true});
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
const p=await browser.newPage({viewport:{width:1600,height:1100}});
const errors=[],records=[];let final;
p.on('pageerror',e=>errors.push(e.message));p.on('filechooser',()=>{});
async function once(action){let r=p.waitForResponse(r=>r.url().endsWith('/evaluate')&&r.request().method()==='POST');await action();r=await r;assert.equal(r.status(),200);final=await r.json();await p.locator('fieldset[aria-label="参数检查器"]:not([disabled])').waitFor({state:'attached'});}
async function num(scope,label,value){const l=scope.getByRole('spinbutton',{name:new RegExp('^'+label+'(?: \\(|$)')});if(Number(await l.inputValue())===value)return;await once(async()=>{await l.fill(String(value));await l.press('Enter');});}
const design=()=>p.getByRole('button',{name:'设计 Design',exact:true}).click();
const manufacture=()=>p.getByRole('button',{name:'制造 Manufacture',exact:true}).click();
const field=()=>p.getByRole('region',{name:'参数场',exact:true});
const mod=name=>p.getByRole('region',{name:'Fabric '+name,exact:true});
async function source(kind,n=401){await design();await field().getByRole('button',{name:'选择图片场 PNG/JPG'}).click();await once(()=>p.getByLabel('选择图片场源文件').setInputFiles(path.join(out,`${kind}-${n}.png`)));await manufacture();}
async function preview(name){const started=Date.now();const r=p.waitForResponse(r=>r.url().endsWith('/fabric/preview'));await p.getByRole('button',{name:'更新3D预览',exact:true}).click();const response=await r;assert.equal(response.status(),200,await response.text());const payload=await response.json();await p.getByRole('button',{name:'三维预览 3D Preview',exact:true}).click();await p.getByText(/Fabric 设计预览已就绪 ·/).waitFor();const readyMs=Date.now()-started;const status=await p.getByText(/Fabric 设计预览已就绪 ·/).textContent();const creationMs=Number(status.match(/实例创建 ([\d.]+) ms/)[1]);await p.getByLabel('预览样式').selectOption('height_map');await p.screenshot({path:path.join(out,name+'.png')});fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify({final,payload,request:response.request().postDataJSON()},null,2));if(name.startsWith('C-')){const box=await p.locator('canvas').boundingBox();await p.mouse.move(box.x+box.width/2,box.y+box.height/2);await p.mouse.wheel(0,-350);await p.waitForTimeout(300);await p.screenshot({path:path.join(out,name+'-zoom.png')});await p.getByRole('button',{name:'适合窗口',exact:true}).click();}if(name==='C-spine'||name==='C-spine-normal'){const by=new Map(payload.instances.filter(i=>i.enabled).map(i=>[`${i.x_mm},${i.y_mm}`,i]));const deltas=[];for(const i of by.values())for(const [x,y] of [[i.x_mm+1,i.y_mm],[i.x_mm,i.y_mm+1]]){const j=by.get(`${x},${y}`);if(j&&Math.min(i.height_mm,j.height_mm)>3)deltas.push(Math.abs(((i.rotation_deg-j.rotation_deg+90)%180+180)%180-90));}assert.ok(deltas.filter(v=>v>45).length<=5);assert.ok(Math.max(...deltas)<=75);}records.push({name,ready_ms:readyMs,instance_creation_ms:creationMs,count:payload.total_count,active:payload.active_count,height:[Math.min(...payload.instances.map(i=>i.height_mm)),Math.max(...payload.instances.map(i=>i.height_mm))]});await manufacture();return payload;}
try{
await p.goto(process.env.F4C_SMOKE_URL || 'http://127.0.0.1:8770');await p.getByRole('banner').getByText('已连接',{exact:true}).waitFor();
await once(()=>p.getByRole('button',{name:'打开示例：基础圆点阵列'}).click());
await field().getByLabel('新增参数场类型').selectOption('distance');await once(()=>field().getByRole('button',{name:'＋ 添加参数场'}).click());
await source('circle');await once(()=>p.getByLabel('Fabric Base 类型').selectOption('solid'));await once(()=>p.getByLabel('Unit Cell 类型').selectOption('fin'));
const cell=p.getByRole('region',{name:'Fabric Unit Cell',exact:true});
await num(cell,'水平间距',1);await num(cell,'垂直间距',1);await num(cell,'单元宽度',.8);await num(cell,'单元深度',.3);
await once(()=>mod('高度').getByRole('checkbox').check());await num(mod('高度'),'最低高度',.5);await num(mod('高度'),'最高高度',8);
await preview('A-circle');
await design();await once(()=>field().getByRole('checkbox',{name:'反转',exact:true}).check());await manufacture();await preview('A-invert');
await design();await once(()=>field().getByRole('checkbox',{name:'反转',exact:true}).uncheck());await once(()=>field().getByRole('checkbox',{name:'自动归一化',exact:true}).uncheck());await num(field(),'最大距离',3);await manufacture();await preview('A-maxdistance');
await design();await num(field(),'遮罩阈值',.75);await once(()=>field().getByRole('checkbox',{name:'自动归一化',exact:true}).check());await manufacture();
await once(()=>mod('比例').getByRole('checkbox').check());await num(mod('比例'),'最小比例',.6);await num(mod('比例'),'最大比例',1.3);
await once(()=>mod('密度').getByRole('checkbox').check());await num(mod('密度'),'显示阈值',.03);
await once(()=>mod('Z 方向').getByRole('checkbox').check());await once(()=>mod('Z 方向').getByLabel('方向模式',{exact:true}).selectOption('gradient'));await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('tangent'));
await source('ring');const tangent=await preview('B-ring-tangent');await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('normal'));const normal=await preview('B-ring-normal');
assert.ok(tangent.instances.some(i=>i.rotation_deg!==0));await num(mod('Z 方向'),'角度偏移',30);await preview('B-offset');await num(mod('Z 方向'),'角度偏移',0);
await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('tangent'));
await source('spine');await preview('C-spine');await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('normal'));await preview('C-spine-normal');await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('tangent'));await source('spine',25);await preview('C-spine-lowres');
await source('circle');
const performance=[];
for(const [count,sx,sy] of [[400,2,2],[1000,2,.8],[5000,.8,.4]]){
await num(cell,'水平间距',sx);await num(cell,'垂直间距',sy);
const started=Date.now();const payload=await preview(`perf-${count}-warmup`);assert.equal(payload.total_count,count);
const warmStarted=Date.now();await preview(`perf-${count}-warm`);
performance.push({count,warm_ready_ms:records.at(-1).ready_ms,instance_creation_ms:records.at(-1).instance_creation_ms,timings_ms:payload.timings_ms});
}
fs.writeFileSync(path.join(out,'browser-performance.json'),JSON.stringify(performance,null,2));
await design();await p.getByRole('button',{name:/试用示例/}).click();await once(()=>p.getByRole('button',{name:'打开示例：参数渐变'}).click());
const effects=p.getByRole('region',{name:'效果堆栈',exact:true});await once(()=>effects.getByRole('button',{name:'＋ 位置/变形'}).click());await num(effects,'偏移 X',2);await num(effects,'偏移 Y',1);
await field().getByLabel('新增参数场类型').selectOption('distance');await once(()=>field().getByRole('button',{name:'＋ 添加参数场'}).click());await source('circle');await once(()=>p.getByLabel('Fabric Base 类型').selectOption('solid'));await once(()=>p.getByLabel('Unit Cell 类型').selectOption('fin'));await once(()=>p.getByLabel('布点方式',{exact:true}).selectOption('pattern_points'));
for(const name of ['高度','Z 方向']){await once(()=>mod(name).getByRole('checkbox').check());const sel=mod(name).getByLabel('驱动参数场',{exact:true});const option=await sel.locator('option').filter({hasText:'distance'}).getAttribute('value');await once(()=>sel.selectOption(option));}
await once(()=>mod('Z 方向').getByLabel('方向模式',{exact:true}).selectOption('gradient'));await once(()=>mod('Z 方向').getByLabel('对齐方式',{exact:true}).selectOption('tangent'));await preview('D-pattern-combined');
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({records,errors},null,2));console.log(JSON.stringify({records,errors},null,2));
}catch(e){await p.screenshot({path:path.join(out,'error.png')});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
