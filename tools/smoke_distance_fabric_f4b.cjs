// Existing internal fixture loader, real HTTP and real Three.js InstancedMesh.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), output = path.join(root, 'work/f4b');
const url = process.env.F4B_SMOKE_URL || 'http://127.0.0.1:8767';
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const report = [];
  try {
    for (const count of [400, 1000, 5000]) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
      const errors = [], requests = [], uploads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() === 'POST' && request.url().endsWith('/evaluate')) requests.push(request);
        if (request.url().endsWith('/assets')) uploads.push(request);
      });
      page.on('filechooser', () => {});
      const once = async action => {
        const response = page.waitForResponse(r => r.url().endsWith('/evaluate') && r.request().method() === 'POST');
        await action(); assert.equal((await response).status(), 200);
        await page.locator('fieldset[aria-label="参数检查器"]:not([disabled])').waitFor({ state: 'attached' });
      };
      const update = async () => {
        const started = Date.now();
        const promise = page.waitForResponse(r => r.url().endsWith('/fabric/preview'));
        await page.getByRole('button', { name: '更新3D预览', exact: true }).click();
        const response = await promise;
        assert.equal(response.status(), 200, await response.text());
        const payload = await response.json();
        await page.getByRole('button', { name: '三维预览 3D Preview', exact: true }).click();
        await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
        const text = await page.getByText(/Fabric 设计预览已就绪 ·/).textContent();
        return { payload, ready_ms: Date.now()-started, instance_creation_ms: Number(text.match(/实例创建 ([\d.]+) ms/)[1]) };
      };
      const manufacture = () => page.getByRole('button', { name: '制造 Manufacture', exact: true }).click();
      const design = () => page.getByRole('button', { name: '设计 Design', exact: true }).click();
      await page.goto(url);
      await page.getByRole('banner').getByText('已连接', { exact: true }).waitFor();
      await once(() => page.getByLabel('选择 PatternDocument 项目文件').setInputFiles(path.join(output, `preview-${count}.pattern.json`)));
      const field = page.getByRole('region', { name: '参数场', exact: true });
      await field.getByRole('button', { name: '选择图片场 PNG/JPG' }).click();
      await once(() => page.getByLabel('选择图片场源文件').setInputFiles(path.join(output, 'black-circle-v1.png')));
      const slider = field.getByRole('slider', { name: '遮罩阈值滑杆' });
      const previous = requests.length;
      await slider.fill('0.6'); assert.equal(requests.length, previous);
      await once(() => slider.dispatchEvent('pointerup')); assert.equal(requests.length, previous+1);
      await manufacture();
      const initial = await update(), payload = initial.payload;
      assert.equal(payload.total_count, count);
      assert.ok(Math.max(...payload.instances.map(i => i.height_mm)) > 7);
      assert.equal(Math.min(...payload.instances.map(i => i.height_mm)), 1);
      assert.ok(new Set(payload.instances.map(i => i.rotation_deg)).size > 10);
      await page.getByLabel('预览样式').selectOption('height_map');
      await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
      if (count === 400) {
        await page.screenshot({ path: path.join(output, 'center-height-tangent.png') });
        await design();
        await once(() => field.getByRole('checkbox', { name: '反转', exact: true }).check());
        await manufacture();
        const inverse = (await update()).payload;
        for (let i = 0; i < payload.instances.length; i++) {
          const a = payload.instances[i], b = inverse.instances[i];
          if (a.height_mm > 1) assert.ok(Math.abs(a.height_mm+b.height_mm-9) < 1e-7);
        }
        await page.screenshot({ path: path.join(output, 'edge-height.png') });
        await design();
        await once(() => field.getByRole('checkbox', { name: '反转', exact: true }).uncheck());
        await field.getByRole('button', { name: '选择图片场 PNG/JPG' }).click();
        await once(() => page.getByLabel('选择图片场源文件').setInputFiles(path.join(output, 'ring-v1.png')));
        await manufacture();
        const tangent = (await update()).payload;
        await page.screenshot({ path: path.join(output, 'ring-fin-tangent.png') });
        await manufacture();
        const orientation = page.getByRole('region', { name: 'Fabric Z 方向', exact: true });
        await once(() => orientation.getByLabel('对齐方式', { exact: true }).selectOption('normal'));
        const normal = (await update()).payload;
        assert.ok(normal.instances.some(i => i.rotation_deg !== 0));
        for (let i = 0; i < normal.instances.length; i++) {
          const a = normal.instances[i], b = tangent.instances[i];
          if (a.rotation_deg || b.rotation_deg) assert.ok(Math.abs(b.rotation_deg-a.rotation_deg-90) < 1e-7);
        }
        await page.screenshot({ path: path.join(output, 'ring-fin-normal.png') });
        await page.getByRole('banner').getByText('已保存', { exact: true }).waitFor();
        await page.reload();
        await page.getByRole('button', { name: '恢复上次编辑', exact: true }).waitFor();
        await once(() => page.getByRole('button', { name: '恢复上次编辑', exact: true }).click());
        await manufacture();
        const restored = (await update()).payload;
        assert.equal(restored.document_revision, normal.document_revision);
        assert.equal(JSON.stringify(restored.instances), JSON.stringify(normal.instances), 'restored transforms must match saved ring preview');
        assert.equal(uploads.length, 3); // circle, ring, refresh ring
      }
      await manufacture();
      const warm = await update();
      assert.deepEqual(errors, []);
      report.push({ count, first_ready_ms: initial.ready_ms, warm_ready_ms: warm.ready_ms,
        instance_creation_ms: initial.instance_creation_ms, timings_ms: payload.timings_ms,
        restore: count === 400, fatal_console_errors: errors });
      await page.close();
    }
    fs.writeFileSync(path.join(output, 'browser-performance.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
