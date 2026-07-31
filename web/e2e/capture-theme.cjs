/* Ad-hoc visual diagnosis: render the live app in the Mass Weed theme vs the
   legacy `dark` theme the user is actually seeing, across the everyday
   surfaces (week view, New-task modal, task detail). Not a test — a camera. */
const { chromium } = require('@playwright/test');
const { seedOrg, login } = require('./seed');
const path = require('path');

const OUT = process.env.OUT || '/tmp/claude-0/-home-user-WEEKLY-WEED-FLOW/ba41908f-0965-5884-8137-0cd2d2eb925a/scratchpad/shots';
const EXE = process.env.PLAYWRIGHT_CHROMIUM_PATH || '/opt/pw-browsers/chromium';

(async () => {
  require('fs').mkdirSync(OUT, { recursive: true });
  const creds = seedOrg();
  const browser = await chromium.launch({ executablePath: EXE });
  const ctx = await browser.newContext({ baseURL: 'http://127.0.0.1:8091', viewport: { width: 1460, height: 900 } });
  const page = await ctx.newPage();

  await login(page, creds.username, creds.password);
  // seed a task so the week view isn't empty
  const title = `Земање примероци | Sampling`;
  await page.getByRole('button', { name: /new task/i }).click();
  await page.locator('#add-title').fill(title);
  await page.getByRole('button', { name: 'Create task' }).click();
  await page.locator('.card-title', { hasText: title }).first().waitFor({ timeout: 10000 });

  async function shoot(theme) {
    await page.evaluate((t) => { try { localStorage.setItem('gf_theme', t); } catch (e) {} }, theme);
    await page.reload({ waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(1200);
    // week view
    await page.screenshot({ path: path.join(OUT, `${theme}-1-week.png`) });
    // new task modal
    await page.getByRole('button', { name: /new task/i }).click().catch(() => {});
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(OUT, `${theme}-2-newtask.png`) });
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(400);
    // expand a card + open detail
    await page.locator('.card-title', { hasText: title }).first().click().catch(() => {});
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /open/i }).first().click().catch(() => {});
    await page.waitForTimeout(900);
    await page.screenshot({ path: path.join(OUT, `${theme}-3-detail.png`) });
    // close detail overlay
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }

  await shoot('mass-weed');
  await shoot('dark');

  await browser.close();
  console.log('done ->', OUT);
})().catch((e) => { console.error(e); process.exit(1); });
