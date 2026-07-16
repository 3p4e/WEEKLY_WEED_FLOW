// @ts-check
// Approvals + My Day: an admin assigns a task to an operator; the operator's
// My Day surfaces the pending acknowledgment and accepting clears it; the
// admin's Approvals view tracks the team pending list either side of the ack.
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string, operator_username: string, operator_id: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('assignment flows through Approvals and My Day acknowledgment', async ({ page, browser }) => {
  const title = `Ack flow ${Date.now()}`;

  await test.step('admin creates + assigns a task, Approvals shows it under team', async () => {
    await login(page, creds.username, creds.password);
    const tid = await page.evaluate(async ({ t, uid }) => {
      const task = await window['GF'].API.createTask({ title: t });
      await window['GF'].API.assign(task.id, uid);
      return task.id;
    }, { t: title, uid: creds.operator_id });
    expect(tid).toBeTruthy();
    await page.locator('.nav-item', { hasText: 'Approvals' }).click();
    await expect(page.locator('.view-title', { hasText: 'Approvals' })).toBeVisible({ timeout: 10_000 });
    const team = page.locator('.apv-row', { hasText: title });
    await expect(team).toBeVisible({ timeout: 10_000 });
  });

  await test.step('operator accepts from My Day; the row clears', async () => {
    const ctx = await browser.newContext();
    const opPage = await ctx.newPage();
    await login(opPage, creds.operator_username, creds.password);
    await opPage.locator('.nav-item', { hasText: 'My Day' }).click();
    const row = opPage.locator('.apv-row', { hasText: title });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await row.getByRole('button', { name: /accept|прифати/i }).click();
    await expect(opPage.locator('.apv-row', { hasText: title })).toHaveCount(0, { timeout: 10_000 });
    await ctx.close();
  });

  await test.step('admin Approvals no longer lists it', async () => {
    await page.evaluate(() => window['GF'].WWF.loadApprovals());
    await expect(page.locator('.apv-row', { hasText: title })).toHaveCount(0, { timeout: 10_000 });
  });
});
