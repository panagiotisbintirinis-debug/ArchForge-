import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';
const [page_html, scene, out, elev, azi, preset] = process.argv.slice(2);
// The pre-installed Chromium (its folder name follows the Playwright version).
const pw = '/opt/pw-browsers';
const exe = fs.readdirSync(pw).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()
  .map(d => [`${pw}/${d}/chrome-linux64/chrome`, `${pw}/${d}/chrome-linux/chrome`]).flat().find(f => fs.existsSync(f));
const browser = await chromium.launch({ executablePath: exe,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
page.on('console', m => { if (m.type() === 'error' || m.type()==='warning') console.log('console:', m.text().slice(0, 300)); });
page.on('pageerror', e => console.log('pageerror:', e.message));
if (process.env.NOAO) await page.addInitScript(() => { window.__noAO = true; });
await page.setContent(fs.readFileSync(page_html, 'utf8'));
await page.waitForFunction(() => !!window.archforgeSetScene, null, { timeout: 60000 });
const payload = JSON.parse(fs.readFileSync(scene, 'utf8'));
// VIEW="x1,y1,x2,y2[,pitch]": eye-level camera at (x1, y1) looking towards (x2, y2).
const view = process.env.VIEW ? process.env.VIEW.split(',').map(Number) : null;
await page.evaluate(([p, e, a, pr, v]) => {
  window.archforgeSetScene(p, true);
  window.setSun(Number(e), Number(a));
  window.setCameraPreset(pr || 'orbit'); if (window.__noAO) window.setAmbientOcclusion(false);
  if (v) window.setViewLine({kind: 'camera', x1: v[0], y1: v[1], x2: v[2], y2: v[3], pitch: v[4] || 0, z: 0});
}, [payload, elev, azi, preset, view]);
await page.waitForTimeout(4000);
await page.screenshot({ path: out });
await browser.close();
