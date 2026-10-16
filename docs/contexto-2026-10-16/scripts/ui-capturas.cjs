const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const mock = require('./mock.json');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.route('http://api.mock/**', r => {
    const u = new URL(r.request().url()); const body = mock[u.pathname];
    r.fulfill({ status: body===undefined?404:200, contentType:'application/json', body: JSON.stringify(body ?? {detail:'nf'}) });
  });
  await p.goto('http://localhost:5173/'); await p.waitForTimeout(2500);
  await p.screenshot({ path: 'operar.png', fullPage: true });
  const tabs = await p.$$eval('[role=tab], .section-tabs button, nav button', els => els.map(e=>e.textContent.trim()));
  console.log(tabs);
  let i=0;
  for (const t of await p.$$('[role=tab]')) { await t.click(); await p.waitForTimeout(1200); await p.screenshot({ path: `tab${i++}.png`, fullPage: true }); }
  await p.setViewportSize({width:390,height:844}); await p.waitForTimeout(800); await p.screenshot({path:'mobile.png', fullPage:false});
  await b.close();
})();
