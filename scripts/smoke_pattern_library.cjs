// Uses the existing browser-test runtime supplied by the caller; no new framework.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const base = (process.env.SMOKE_BASE_URL || "http://127.0.0.1:8777").replace(/\/$/, "");
const output = path.resolve(process.env.SMOKE_OUTPUT || "work/pattern-library-smoke");
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: "msedge", args: ["--no-proxy-server"] });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    const page = await context.newPage();
    const errors = [], failedResources = [], externalRequests = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) failedResources.push([response.status(), response.url()]); });
    page.on("request", request => {
      const url = request.url();
      if (/^https?:/.test(url) && new URL(url).origin !== new URL(base).origin) externalRequests.push(url);
    });
    await page.goto(base + "/", { waitUntil: "domcontentloaded" });
    const link = page.getByRole("link", { name: "小芒图案库 ↗" });
    await link.waitFor();
    assert.equal(await link.getAttribute("target"), "_blank");
    const popupEvent = page.waitForEvent("popup");
    await link.click();
    const library = await popupEvent;
    await library.waitForURL(base + "/patterns/");
    await library.close();
    await page.goto(base + "/patterns/");
    await page.locator(".samples a.pattern").first().waitFor();
    // Upstream initially renders 20 placeholders and fetches the full gallery.
    // Wait for its real data instead of assuming local-network hydration speed.
    await page.waitForFunction(() => document.querySelectorAll(".samples a.pattern").length === 330);
    assert.equal(await page.locator(".samples a.pattern").count(), 330);
    assert.match(await page.title(), /小芒图案库/);
    await page.screenshot({ path: path.join(output, "gallery.png") });
    await page.locator("#search").fill("waves");
    await page.waitForFunction(() => document.querySelectorAll(".samples a.pattern").length < 330);
    assert.ok(await page.locator(".samples a.pattern").count() > 0);
    await page.locator("#search").fill("");
    await page.waitForFunction(() => document.querySelectorAll(".samples a.pattern").length === 330);
    const results = [];
    for (const slug of ["waves-1", "circles-1", "diamonds-14"]) {
      await page.locator('.samples a.pattern[href="' + slug + '/"]').click();
      await page.locator(".pcr-button").first().waitFor();
      const before = await page.locator(".preview").getAttribute("style");
      await page.locator("#scale").fill("3");
      await page.locator("#angle").fill("35");
      const horizontalSpacing = page.locator("#hspacing");
      if (await horizontalSpacing.count()) await horizontalSpacing.fill("2");
      assert.notEqual(await page.locator(".preview").getAttribute("style"), before);
      // The upstream has separate responsive export bars. Exercise visible buttons.
      await page.locator('.dimensionGrid input[title="宽度"]:visible').fill("480");
      await page.locator('.dimensionGrid input[title="高度"]:visible').fill("320");
      const svgEvent = page.waitForEvent("download");
      await page.locator('.downloadGrid button:visible').filter({ hasText: /^SVG$/ }).click();
      const svgDownload = await svgEvent;
      const svgPath = path.join(output, slug + ".svg");
      await svgDownload.saveAs(svgPath);
      const svg = fs.readFileSync(svgPath, "utf8");
      const parsed = await page.evaluate(text => {
        const doc = new DOMParser().parseFromString(text, "image/svg+xml");
        return { error: !!doc.querySelector("parsererror"), width: doc.documentElement.getAttribute("width"),
          height: doc.documentElement.getAttribute("height"),
          transform: doc.querySelector("pattern").getAttribute("patternTransform"),
          paths: doc.querySelectorAll("path").length };
      }, svg);
      assert.equal(parsed.error, false);
      assert.equal(parsed.width, "480");
      assert.equal(parsed.height, "320");
      assert.equal(parsed.transform, "scale(3) rotate(35)");
      assert.ok(parsed.paths > 0);
      const pngEvent = page.waitForEvent("download");
      await page.locator('.downloadGrid button:visible').filter({ hasText: /^PNG$/ }).click();
      const pngDownload = await pngEvent;
      const pngPath = path.join(output, slug + ".png");
      await pngDownload.saveAs(pngPath);
      const png = fs.readFileSync(pngPath);
      assert.equal(png.subarray(1, 4).toString(), "PNG");
      assert.equal(png.readUInt32BE(16), 480);
      assert.equal(png.readUInt32BE(20), 320);
      // Open both real downloaded artifacts in the browser and compare pixels.
      const pixels = await page.evaluate(async ({ svg, png }) => {
        async function render(url) {
          const image = new Image();
          image.src = url;
          await image.decode();
          const canvas = document.createElement("canvas");
          canvas.width = 480; canvas.height = 320;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(image, 0, 0);
          return ctx.getImageData(0, 0, 480, 320).data;
        }
        const a = await render("data:image/svg+xml;base64," + svg);
        const b = await render("data:image/png;base64," + png);
        let varied = 0, differing = 0;
        for (let i = 0; i < a.length; i += 4) {
          if (b[i] !== b[0] || b[i + 1] !== b[1] || b[i + 2] !== b[2]) varied++;
          if (Math.abs(a[i] - b[i]) > 3 || Math.abs(a[i + 1] - b[i + 1]) > 3 || Math.abs(a[i + 2] - b[i + 2]) > 3) differing++;
        }
        return { varied, differing, total: 480 * 320 };
      }, { svg: Buffer.from(svg).toString("base64"), png: png.toString("base64") });
      assert.ok(pixels.varied > 100, "PNG must contain the pattern, not a blank rectangle");
      assert.ok(pixels.differing / pixels.total < 0.01, "SVG and PNG must match current parameters");
      await page.screenshot({ path: path.join(output, slug + "-editor.png") });
      await page.reload();
      await page.locator(".pcr-button").first().waitFor();
      assert.match(await page.title(), new RegExp(slug.split("-")[0], "i"));
      results.push({ slug, svgBytes: Buffer.byteLength(svg), pngBytes: png.length, ...pixels, refresh: "PASS" });
      await page.locator('nav a[href="."]').click();
      await page.waitForFunction(() => document.querySelectorAll(".samples a.pattern").length === 330);
    }
    // Mobile responsive controls and export are the same original editor.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + "/patterns/circles-1/");
    await page.locator(".pcr-button").first().waitFor();
    const mobileEvent = page.waitForEvent("download");
    await page.locator(".downloadGrid button:visible").filter({ hasText: /^SVG$/ }).click();
    await (await mobileEvent).saveAs(path.join(output, "mobile.svg"));
    await page.screenshot({ path: path.join(output, "mobile.png") });
    // Return through the real module link, then exercise the unchanged STL path.
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole("link", { name: "← 返回图案实验室" }).click();
    await page.getByRole("banner").getByText("已连接", { exact: true }).waitFor();
    const evaluation = page.waitForResponse(response => response.url().endsWith("/evaluate") && response.request().method() === "POST");
    await page.getByRole("button", { name: "打开示例：基础圆点阵列" }).click();
    assert.equal((await evaluation).status(), 200);
    await page.getByRole("button", { name: "制造 Manufacture", exact: true }).click();
    const buildEvent = page.waitForResponse(response => response.url().endsWith("/manufacturing/build"));
    await page.getByRole("button", { name: "检查并生成", exact: true }).click();
    const build = await buildEvent;
    assert.equal(build.status(), 200, await build.text());
    const standardResult = await build.json();
    const stlEvent = page.waitForEvent("download");
    const stlResponseEvent = page.waitForResponse(response => response.url().endsWith("/model.stl"));
    await page.getByRole("button", { name: "导出 STL", exact: true }).click();
    const stlResponse = await stlResponseEvent;
    assert.equal(stlResponse.status(), 200);
    const stlDownload = await stlEvent;
    assert.equal(await stlDownload.failure(), null);
    await stlDownload.saveAs(path.join(output, "standard.stl"));
    const stl = fs.readFileSync(path.join(output, "standard.stl"));
    assert.equal(stl.length, 84 + 50 * stl.readUInt32LE(80));
    const standard = { status: build.status(), result: standardResult,
      downloadStatus: stlResponse.status(), bytes: stl.length, triangles: stl.readUInt32LE(80) };
    assert.deepEqual(errors, []);
    assert.deepEqual(failedResources, []);
    assert.deepEqual(externalRequests, [], "No advertising, tracking, or personal-service requests");
    const report = { base, gallery: 330, selection: "PASS", search: "PASS", navigation: "PASS",
      results, mobile: "PASS", standard, errors, failedResources, externalRequests };
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
