/* Sweep the app's surfaces under the (now exclusive) Mass Weed theme and
   screenshot each — visual evidence for the theme-coverage audit. */
const { chromium } = require('@playwright/test');
const { seedOrg, login } = require('./seed');
const path = require('path');

const OUT = process.env.OUT || '/tmp/claude-0/-home-user-WEEKLY-WEED-FLOW/ba41908f-0965-5884-8137-0cd2d2eb925a/scratchpad/shots/sweep';
const EXE = process.env.PLAYWRIGHT_CHROMIUM_PATH || '/opt/pw-browsers/chromium';

(async () => {
  require('fs').mkdirSync(OUT, { recursive: true });
  const creds = seedOrg();
  const browser = await chromium.launch({ executablePath: EXE });
  const ctx = await browser.newContext({ baseURL: 'http://127.0.0.1:8091', viewport: { width: 1460, height: 900 } });
  const page = await ctx.newPage();
  await login(page, creds.username, creds.password);
  await page.waitForTimeout(600);

  const shot = (n) => page.screenshot({ path: path.join(OUT, n + '.png') });

  // seed one task so views have content
  const title = 'Приемен преглед | Intake inspection';
  await page.getByRole('button', { name: /new task/i }).click();
  await page.locator('#add-title').fill(title);
  await page.getByRole('button', { name: 'Create task' }).click();
  await page.locator('.card-title', { hasText: title }).first().waitFor({ timeout: 10000 });

  // expanded card
  await page.locator('.card-title', { hasText: title }).first().click();
  await page.waitForTimeout(400);
  await shot('01-card-expanded');

  // worklog modal
  await page.getByRole('button', { name: /log work/i }).first().click().catch(() => {});
  await page.waitForTimeout(500);
  await shot('02-worklog');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  // views by nav
  const views = [['board', 'Board'], ['timeline', 'Timeline'], ['calendar', 'Calendar'],
    ['myday', 'My Day'], ['team', 'Executive'], ['approvals', 'Approvals'],
    ['execreport', 'Executive Report'], ['analytics', 'Analytics'], ['report', 'Report'],
    ['facility', 'Facility'], ['cultivation', 'Cultivation'], ['harvest', 'Harvest'],
    ['decon', 'Decontamination'], ['waste', 'Destruction'], ['notifications', 'Coordination'],
    ['depthome', 'My Department']];
  let i = 3;
  for (const [key, label] of views) {
    const n = String(i++).padStart(2, '0');
    const ok = await page.evaluate((k) => { try { window.GF.setView(k); return !!window.GF.state; } catch (e) { return false; } }, key);
    await page.waitForTimeout(650);
    await shot(`${n}-view-${key}${ok ? '' : '-FAILED'}`);
  }

  // settings modal
  await page.evaluate(() => { try { window.GF.openSettings('prefs'); } catch (e) {} });
  await page.waitForTimeout(500);
  await shot('90-settings');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  // theme picker
  await page.evaluate(() => { try { window.GF.openThemePicker(); } catch (e) {} });
  await page.waitForTimeout(500);
  await shot('91-theme-picker');
  await page.keyboard.press('Escape');

  await browser.close();
  console.log('sweep done ->', OUT);
})().catch((e) => { console.error(e); process.exit(1); });
