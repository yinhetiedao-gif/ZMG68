// Actual production UI, no internal JSON loader or mocked HTTP.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = path.resolve(__dirname, '../work/f4b');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('filechooser', () => {});
    const once = async action => {
      const response = page.waitForResponse(r => r.url().endsWith('/evaluate') && r.request().method() === 'POST');
      await action(); assert.equal((await response).status(), 200);
      await page.locator('fieldset[aria-label="参数检查器"]:not([disabled])').waitFor({ state: 'attached' });
    };
    await page.goto(process.env.F4B_PUBLIC_URL || 'http://127.0.0.1:8768');
    await page.getByRole('banner').getByText('已连接', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('选择 PatternDocument 项目文件').count(), 0);
    await once(() => page.getByRole('button', { name: '打开示例：基础圆点阵列' }).click());
    const field = page.getByRole('region', { name: '参数场', exact: true });
    await field.getByLabel('新增参数场类型').selectOption('distance');
    await once(() => field.getByRole('button', { name: '＋ 添加参数场' }).click());
    await field.getByRole('button', { name: '选择图片场 PNG/JPG' }).click();
    await once(() => page.getByLabel('选择图片场源文件').setInputFiles(path.join(output, 'black-circle-v1.png')));
    await page.getByRole('button', { name: '制造 Manufacture', exact: true }).click();
    await once(() => page.getByLabel('Fabric Base 类型').selectOption('solid'));
    await once(() => page.getByLabel('Unit Cell 类型').selectOption('fin'));
    for (const name of ['Fabric 高度', 'Fabric 比例', 'Fabric Z 方向'])
      await once(() => page.getByRole('region', { name, exact: true }).getByRole('checkbox').check());
    const orientation = page.getByRole('region', { name: 'Fabric Z 方向', exact: true });
    await once(() => orientation.getByLabel('方向模式', { exact: true }).selectOption('gradient'));
    assert.equal(await orientation.getByLabel('最小角度', { exact: true }).count(), 0);
    await once(() => orientation.getByLabel('对齐方式', { exact: true }).selectOption('tangent'));
    const response = page.waitForResponse(r => r.url().endsWith('/fabric/preview'));
    await page.getByRole('button', { name: '更新3D预览', exact: true }).click();
    const received = await response; assert.equal(received.status(), 200);
    const result = await received.json();
    assert.ok(new Set(result.instances.map(i => i.height_mm)).size > 1);
    assert.ok(new Set(result.instances.map(i => i.rotation_deg)).size > 1);
    await page.getByRole('button', { name: '三维预览 3D Preview', exact: true }).click();
    await page.getByText(/Fabric 设计预览已就绪 ·/).waitFor();
    await page.screenshot({ path: path.join(output, 'production-distance-ui.png') });
    assert.deepEqual(errors, []);
    const report = { production_ui: 'PASS', generic_distance_controls: 'PASS', gradient_tangent: 'PASS',
      total_count: result.total_count, console_fatal_errors: errors };
    fs.writeFileSync(path.join(output, 'production-ui.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
