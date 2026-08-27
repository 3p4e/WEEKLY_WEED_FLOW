/* Prove the exclusive-Mass-Weed boot healing: seed the stale gf_theme values a
   real user may carry (the owner's browser has 'dark') BEFORE load, then load
   and assert + screenshot what actually paints. */
const { chromium } = require('@playwright/test');
const { seedOrg, login } = require('./seed');
const path = require('path');

const OUT = process.env.OUT || '/tmp/claude-0/-home-user-WEEKLY-WEED-FLOW/ba41908f-0965-5884-8137-0cd2d2eb925a/scratchpad/shots';
const EXE = process.env.PLAYWRIGHT_CHROMIUM_PATH || '/opt/pw-browsers/chromium';

(async () => {
  require('fs').mkdirSync(OUT, { recursive: true });
  const creds = seedOrg();
  const browser = await chromium.launch({ executablePath: EXE });

  async function run(saved, shotName) {
    const ctx = await browser.newContext({ baseURL: 'http://127.0.0.1:8091', viewport: { width: 1460, height: 900 } });
    const page = await ctx.newPage();
    // seed the stale value before ANY app code runs. Also seed the CURRENT
    // schema version — the owner's browser has it, and without it boot-guard
    // wipes all gf_* keys (a fresh profile can't carry a stale theme anyway).
    await page.addInitScript((t) => { try {
      localStorage.setItem('gf_schema_version', '2026-06-01-r5');
      localStorage.setItem('gf_theme', t);
    } catch (e) {} }, saved);
    await login(page, creds.username, creds.password);
    await page.waitForTimeout(800);
    const state = await page.evaluate(() => ({
      domTheme: document.documentElement.dataset.theme,
      savedTheme: localStorage.getItem('gf_theme'),
    }));
    console.log(`saved='${saved}' -> dom='${state.domTheme}' persisted='${state.savedTheme}'`);
    await page.screenshot({ path: path.join(OUT, shotName) });
    await ctx.close();
    return state;
  }

  const a = await run('dark', 'migrated-from-dark.png');       // the owner's case
  const b = await run('light', 'migrated-from-light.png');     // brightness preserved
  const c = await run('nord', 'migrated-from-nord.png');       // carbon retiree

  const ok = a.domTheme === 'mass-weed' && a.savedTheme === 'mass-weed'
    && b.domTheme === 'mass-weed-light' && b.savedTheme === 'mass-weed-light'
    && c.domTheme === 'mass-weed' && c.savedTheme === 'mass-weed';
  console.log(ok ? 'MIGRATION OK' : 'MIGRATION BROKEN');
  await browser.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(1); });
