// Clicks in the application's real 3D page (pbr_page_html + scene_payload) in headless Chromium and prints what
// the page sends to Python through the bridge — without Qt or a GPU (software WebGL).
//
// Usage: node scripts/toolbox/click_3d.mjs <page.html> <scene.json> <tool> [cols] [rows] [preset]
//   tool   = the 3D tool to activate (window.setActiveTool), e.g. paint_material
//   cols × rows = grid of clicks (press + release in place) over the canvas (default 24 × 14)
//   preset = camera preset (default orbit)
// Output (stdout): one JSON line {"calls": [[method, ...args], ...]} — every bridge call the clicks made.
// Python side: archforge/scenarios/click3d.py writes the files and runs this (tests skip without Chromium).
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';

const [pageHtml, sceneJson, tool, cols = '24', rows = '14', preset = 'orbit'] = process.argv.slice(2);
const pw = '/opt/pw-browsers';
const exe = fs.readdirSync(pw).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()
  .map(d => [`${pw}/${d}/chrome-linux64/chrome`, `${pw}/${d}/chrome-linux/chrome`]).flat().find(f => fs.existsSync(f));
const browser = await chromium.launch({ executablePath: exe,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1000, height: 640 } });
page.on('pageerror', e => console.error('pageerror:', e.message));
// A stand-in for Qt's QWebChannel: every bridge method call is recorded.
await page.addInitScript(() => {
  window.__calls = [];
  const bridge = new Proxy({}, { get: (_t, name) => (...args) => { window.__calls.push([String(name), ...args]); } });
  window.qt = { webChannelTransport: {} };
  window.QWebChannel = function (_transport, ready) { ready({ objects: { renderBridge: bridge } }); };
});
await page.setContent(fs.readFileSync(pageHtml, 'utf8'));
await page.waitForFunction(() => !!window.archforgeSetScene, null, { timeout: 60000 });
const payload = JSON.parse(fs.readFileSync(sceneJson, 'utf8'));
await page.evaluate(([p, pr, t]) => {
  window.archforgeSetScene(p, true);
  window.setCameraPreset(pr);
  window.setActiveTool(t);
}, [payload, preset, tool]);
await page.waitForTimeout(1500);
await page.evaluate(() => { window.__calls = []; });
const canvas = await page.$('canvas');
const box = await canvas.boundingBox();
for (let r = 1; r <= Number(rows); r++) {
  for (let c = 1; c <= Number(cols); c++) {
    const x = box.x + box.width * c / (Number(cols) + 1), y = box.y + box.height * r / (Number(rows) + 1);
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.up();
  }
}
console.log(JSON.stringify({ calls: await page.evaluate(() => window.__calls) }));
await browser.close();
