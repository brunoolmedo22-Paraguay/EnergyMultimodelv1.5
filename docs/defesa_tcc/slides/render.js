const { chromium } = require('playwright');
const path = require('path'); const fs = require('fs');
(async () => {
  const dir = __dirname; const out = path.join(dir, 'png'); fs.mkdirSync(out, { recursive: true });
  const files = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync(dir).filter(f => /^[A-Z]_.*\.html$/.test(f));
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const f of files) {
    await p.goto('file://' + path.join(dir, f)); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(out, f.replace('.html', '.png')) }); console.log('ok', f);
  }
  await b.close();
})();
