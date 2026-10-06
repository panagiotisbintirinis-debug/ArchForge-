const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [mode, w, h, from, to] = [process.argv[2] || 'stills', +(process.argv[3] || 720), +(process.argv[4] || 1280), +(process.argv[5] || 0), +(process.argv[6] || 1e9)];
  const browser = await chromium.launch({ args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on('console', m => { if (m.type() === 'error') console.log('ERR', m.text()); });
  page.on('pageerror', e => console.log('PAGEERR', e.message));
  await page.goto('file://' + path.resolve(__dirname, 'film.html') + `?capture=1&w=${w}&h=${h}`);
  await page.waitForFunction(() => !!window.render);
  const stage = await page.$('#stage');
  if (mode === 'stills') {
    for (const t of (process.argv[7] || '2,6,9,11.5,12.8,14.8,16.5,18.5,21,24.5').split(',').map(Number)) {
      const t0 = Date.now();
      await page.evaluate(t => window.render(t), t);
      await stage.screenshot({ path: `s_${t}.png` });
      console.log('t', t, (Date.now() - t0) + 'ms');
    }
  } else {
    const fps = 30, total = Math.round(25 * fps) + 30;
    for (let i = Math.max(0, from); i < Math.min(total, to); i++) {
      await page.evaluate(t => window.render(t), Math.min(i / fps, 25));
      await stage.screenshot({ path: `' + (process.env.FRAMES || 'frames') + '/f${String(i).padStart(4, '0')}.png` });
    }
  }
  await browser.close();
})();
