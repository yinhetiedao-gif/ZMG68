// Public production UI, no fixture loader, no mocked API or renderer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const url = process.env.F4A_SMOKE_URL || 'http://127.0.0.1:8766';
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], badApi = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.url().includes('/api/') && !r.ok()) badApi.push(`${r.status()} ${r.url()}`); });
    page.on('filechooser', () => {});
    const ready = () => page.locator('fieldset[aria-label="参数检查器"]:not([disabled])').waitFor({ state: 'attached' });
    const once = async action => {
      const response = page.waitForResponse(r => r.url().endsWith('/evaluate') && r.request().method() === 'POST');
      await action(); assert.equal((await response).status(), 200); await ready();
    };
    const update = async () => {
      const response = page.waitForResponse(r => r.url().endsWith('/fabric/preview'));
      await page.getByRole('button', { name: '更新3D预览', exact: true }).click();
      const result = await response;
      assert.equal(result.status(), 200);
      return result.json();
    };
    await page.goto(url);
    await page.getByRole('banner').getByText('已连接', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('选择 PatternDocument 项目文件').count(), 0);
    await once(() => page.getByRole('button', { name: '打开示例：基础圆点阵列' }).click());
    const field = page.getByRole('region', { name: '参数场', exact: true });
    await field.getByLabel('新增参数场类型').selectOption('image');
    await once(() => field.getByRole('button', { name: '＋ 添加参数场' }).click());
    await field.getByRole('button', { name: '选择图片场 PNG/JPG' }).click();
    await once(() => page.getByLabel('选择图片场源文件').setInputFiles(path.join(root, 'work/f4a/black-circle-v1.png')));
    assert.equal(await field.getByRole('checkbox', { name: /黑色为 1/ }).isChecked(), true);
    await page.getByRole('button', { name: '制造 Manufacture', exact: true }).click();
    await once(() => page.getByLabel('Fabric Base 类型').selectOption('solid'));
    await once(() => page.getByLabel('Unit Cell 类型').selectOption('fin'));
    await once(() => page.getByLabel('布点方式').selectOption('pattern_points'));
    for (const name of ['Fabric 高度', 'Fabric 比例', 'Fabric 密度']) {
      await once(() => page.getByRole('region', { name, exact: true }).getByRole('checkbox').check());
    }
    const result = await update();
    assert.equal(result.total_count, 9);
    assert.ok(result.active_count > 0 && result.active_count < 9);
    assert.ok(new Set(result.instances.map(i => i.height_mm)).size > 1);
    assert.ok(new Set(result.instances.map(i => i.scale)).size > 1);
    await page.getByRole('button', { name: '三维预览 3D Preview', exact: true }).click();
    await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
    await page.getByLabel('预览样式').selectOption('high_contrast');
    await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
    await page.screenshot({ path: path.join(root, 'work/f4a/public-ui-pattern-points.png') });
    // Import and automatic reuse of the original raster as Shared Field source.
    await page.getByRole('button', { name: '设计 Design', exact: true }).click();
    await once(() => page.getByLabel('选择 PNG 或 JPG 图片').setInputFiles(path.join(root, 'work/f4a/black-circle-v1.png')));
    await field.getByLabel('新增参数场类型').selectOption('image');
    await once(() => field.getByRole('button', { name: '＋ 添加参数场' }).click());
    await field.getByText('源图片：black-circle-v1.png', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    assert.deepEqual(badApi, []);
    const report = { public_ui: 'PASS', image_source_import_reuse: 'PASS', pattern_points: result.total_count,
      density_visible: result.active_count, height_range: [Math.min(...result.instances.map(i => i.height_mm)),
        Math.max(...result.instances.map(i => i.height_mm))], console_fatal_errors: errors, bad_api: badApi };
    fs.writeFileSync(path.join(root, 'work/f4a/public-ui-smoke.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
