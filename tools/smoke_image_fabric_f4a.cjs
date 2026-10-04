// Existing test-only file loader + real API + production Three.js renderer.
// npm run build -- --mode test; PLAYWRIGHT_MODULE points to the existing runtime.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const url = process.env.F4A_SMOKE_URL || 'http://127.0.0.1:8766';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const report = [];
  try {
    for (const count of [400, 1000, 5000]) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
      const errors = [], posts = [], uploads = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() === 'POST' && request.url().endsWith('/evaluate')) posts.push(request);
        if (request.url().endsWith('/assets')) uploads.push(request);
      });
      const ready = () => page.locator('fieldset[aria-label="参数检查器"]:not([disabled])').waitFor();
      const evaluateOnce = async action => {
        const response = page.waitForResponse(r => r.url().endsWith('/evaluate') && r.request().method() === 'POST');
        await action();
        assert.equal((await response).status(), 200);
        await ready();
      };
      await page.goto(url);
      await page.getByRole('banner').getByText('已连接', { exact: true }).waitFor();
      await evaluateOnce(() => page.getByLabel('选择 PatternDocument 项目文件').setInputFiles(
        path.join(root, 'work/f4a', `preview-${count}.pattern.json`)));
      const field = page.getByRole('region', { name: '参数场', exact: true });
      page.on('filechooser', () => {}); // No Windows native chooser.
      await field.getByRole('button', { name: '选择图片场 PNG/JPG' }).click();
      await evaluateOnce(() => page.getByLabel('选择图片场源文件').setInputFiles(
        path.join(root, 'work/f4a/black-circle-v1.png')));
      assert.equal(uploads.length, 1);
      // Image Schema slider: no evaluate until release, exactly one after release.
      const slider = field.getByRole('slider', { name: '遮罩阈值滑杆' });
      const before = posts.length;
      await slider.fill('0.6');
      assert.equal(posts.length, before);
      await evaluateOnce(() => slider.dispatchEvent('pointerup'));
      assert.equal(posts.length, before + 1);
      await page.getByRole('button', { name: '制造 Manufacture', exact: true }).click();
      const started = Date.now();
      const responsePromise = page.waitForResponse(r => r.url().endsWith('/fabric/preview'));
      await page.getByRole('button', { name: '更新3D预览', exact: true }).click();
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      const payload = await response.json();
      assert.equal(payload.total_count, count);
      assert.equal(payload.active_count, count);
      assert.equal(Math.max(...payload.instances.map(i => i.height_mm)), 8);
      assert.equal(Math.min(...payload.instances.map(i => i.height_mm)), 1);
      assert.equal(Math.max(...payload.instances.map(i => i.scale)), 2);
      assert.equal(Math.min(...payload.instances.map(i => i.scale)), .5);
      const api_ms = Date.now() - started;
      await page.getByRole('button', { name: '三维预览 3D Preview', exact: true }).click();
      await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
      const status = await page.getByText(/Fabric 设计预览已就绪 ·/).textContent();
      const browser_ms = Number(status.match(/实例创建 ([\d.]+) ms/)[1]);
      const total_ready_ms = Date.now() - started;
      if (count === 400) {
        await page.getByLabel('预览样式').selectOption('height_map');
        await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
        await page.screenshot({ path: path.join(root, 'work/f4a/image-height-scale-preview.png') });
        // IndexedDB refresh recovery must re-upload with unchanged design state.
        await page.reload();
        await page.getByRole('button', { name: '恢复上次编辑', exact: true }).waitFor();
        await evaluateOnce(() => page.getByRole('button', { name: '恢复上次编辑', exact: true }).click());
        assert.equal(uploads.length, 2);
        await page.getByRole('button', { name: '制造 Manufacture', exact: true }).click();
        const recovered = page.waitForResponse(r => r.url().endsWith('/fabric/preview'));
        await page.getByRole('button', { name: '更新3D预览', exact: true }).click();
        const restored = await (await recovered).json();
        assert.deepEqual(restored.instances, payload.instances);
        assert.equal(restored.document_revision, payload.document_revision);
      }
      assert.deepEqual(errors, []);
      report.push({ count, api_ms, browser_ms, total_ready_ms, timings_ms: payload.timings_ms,
        restored: count === 400, console_fatal_errors: errors });
      await page.close();
    }
    fs.writeFileSync(path.join(root, 'work/f4a/browser-performance.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
