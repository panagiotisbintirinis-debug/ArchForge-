import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';
const [page_html, scene, out, elev, azi, preset] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
page.on('console', m => { if (m.type() === 'error' || m.type()==='warning') console.log('console:', m.text().slice(0, 300)); });
page.on('pageerror', e => console.log('pageerror:', e.message));
if (process.env.NOAO) await page.addInitScript(() => { window.__noAO = true; });
await page.setContent(fs.readFileSync(page_html, 'utf8'));
await page.waitForFunction(() => !!window.archforgeSetScene, null, { timeout: 60000 });
const payload = JSON.parse(fs.readFileSync(scene, 'utf8'));
await page.evaluate(([p, e, a, pr]) => {
  window.archforgeSetScene(p, true);
  window.setSun(Number(e), Number(a));
  window.setCameraPreset(pr || 'orbit'); if (window.__noAO) window.setAmbientOcclusion(false);
}, [payload, elev, azi, preset]);
await page.waitForTimeout(4000);
await page.screenshot({ path: out });
await browser.close();
