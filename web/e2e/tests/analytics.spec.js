// @ts-check
// Analytics view: KPI tiles, the created-vs-completed chart with its legend,
// the on-time line, department + type breakdowns — and, per the owner's
// decision, not a single hour metric anywhere on the screen.
const { test, expect } = require('@playwright/test');
const { seedOrg, login, gotoModule } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('analytics view renders trends without hour metrics', async ({ page }) => {
  const stamp = Date.now();

  await login(page, creds.username, creds.password);

  await test.step('seed one completed-on-time and one open task via the API client', async () => {
    await page.evaluate(async (s) => {
      const today = new Date().toISOString().slice(0, 10);
      const a = await GF.API.createTask({ title: `Ana done ${s}`, task_type: 'lab', due_date: today });
      await GF.API.updateTask(a.id, { status: 'completed' });
      await GF.API.createTask({ title: `Ana open ${s}`, task_type: 'capa', due_date: today });
    }, stamp);
  });

  await test.step('open Analytics from the rail', async () => {
    await gotoModule(page, 'analytics');   // Analytics lives in the analytics module
    await page.locator('[data-nav="analytics"]').click();
    await expect(page.locator('.ana-tiles .ana-tile')).toHaveCount(4, { timeout: 15_000 });
  });

  await test.step('charts render with legend and data marks', async () => {
    // two-series chart carries a legend (identity never color-alone)
    await expect(page.locator('.ana-legend span')).toHaveCount(2);
    // grouped bars exist (SVG paths with the chart tokens)
    expect(await page.locator('.ana-panel svg path[fill="var(--ch-a)"]').count()).toBeGreaterThan(0);
    expect(await page.locator('.ana-panel svg path[fill="var(--ch-b)"]').count()).toBeGreaterThan(0);
    // dept + type rows show the seeded open task
    await expect(page.locator('.ana-row').first()).toBeVisible();
  });

  await test.step('no hour metrics anywhere', async () => {
    const text = await page.locator('#view-root, main, body').first().innerText();
    expect(text).not.toMatch(/hours?\s+(logged|spent)/i);
    expect(text).not.toMatch(/\d+(\.\d+)?\s*h\b/);
  });

  await test.step('range toggle refetches', async () => {
    await page.locator('.ana-head .ntf-tab', { hasText: '12' }).click();
    await expect(page.locator('.ana-head .ntf-tab.on', { hasText: '12' })).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.ana-tiles .ana-tile')).toHaveCount(4);
  });
});
