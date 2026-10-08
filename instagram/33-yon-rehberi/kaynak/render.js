const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
  await p.goto('file://' + process.argv[2]);
  await p.evaluate(() => document.fonts.ready);
  for (let i = 1; i <= 7; i++) {
    await p.locator('#s' + i).screenshot({ path: process.argv[3] + '/' + String(i).padStart(2, '0') + '.png' });
  }
  await b.close();
})();
