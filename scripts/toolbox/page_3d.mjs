// Runs a script in the application's real 3D page (pbr_page_html + scene_payload) in headless Chromium — without Qt or
// a GPU (software WebGL) — and prints what it returns.  Bridge calls the page makes to Python are recorded in
// window.__calls (a stand-in for Qt's QWebChannel).
//
// Usage: node scripts/toolbox/page_3d.mjs <page.html> <scene.json> <script.js> [width] [height]
//   script.js = the body of an async function run in the page after the scene is set; `payload` is the scene.
// Output (stdout): one JSON line {"result": <what the script returned>}.
// Python side: archforge/scenarios/click3d.py (run_in_page, clicks); tests skip without Chromium.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'fs';

const [pageHtml, sceneJson, scriptJs, width = '800', height = '520'] = process.argv.slice(2);
const pw = '/opt/pw-browsers';
const exe = fs.readdirSync(pw).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()
  .map(d => [`${pw}/${d}/chrome-linux64/chrome`, `${pw}/${d}/chrome-linux/chrome`]).flat().find(f => fs.existsSync(f));
const browser = await chromium.launch({ executablePath: exe,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: Number(width), height: Number(height) } });
page.on('pageerror', e => console.error('pageerror:', e.message));
await page.addInitScript(() => {
  window.__calls = [];
  const bridge = new Proxy({}, { get: (_t, name) => (...args) => { window.__calls.push([String(name), ...args]); } });
  window.qt = { webChannelTransport: {} };
  // Asynchronous, as Qt's: the page's own `let bridge` exists by the time the callback runs.
  window.QWebChannel = function (_transport, ready) { setTimeout(() => ready({ objects: { renderBridge: bridge } }), 0); };
});
await page.goto('file://' + pageHtml);       // setContent would skip the init script above
await page.waitForFunction(() => !!window.archforgeSetScene, null, { timeout: 60000 });
const payload = JSON.parse(fs.readFileSync(sceneJson, 'utf8'));
await page.evaluate((p) => { window.archforgeSetScene(p, true); }, payload);
const body = fs.readFileSync(scriptJs, 'utf8');
const result = await page.evaluate(([b, p]) => (new Function('payload', 'return (async () => {' + b + '})();'))(p),
                                   [body, payload]);
console.log(JSON.stringify({ result }));
await browser.close();
