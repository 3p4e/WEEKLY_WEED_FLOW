// @ts-check
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string, teammate_name: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('login, create a task, cycle its status, assign a teammate, logout', async ({ page }) => {
  const taskTitle = `E2E task ${Date.now()}`;

  await test.step('login', async () => {
    await login(page, creds.username, creds.password);
  });

  await test.step('create a task', async () => {
    await page.getByRole('button', { name: /new task/i }).click();
    await page.locator('#add-title').fill(taskTitle);
    await page.getByRole('button', { name: 'Create task' }).click();
    await expect(page.locator('.card-title', { hasText: taskTitle })).toBeVisible({ timeout: 10_000 });
  });

  const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });

  await test.step('cycle its status', async () => {
    const pill = card.locator('.pill');
    const before = await pill.getAttribute('class');
    await pill.click();
    await expect(pill).not.toHaveClass(before ?? '');
  });

  await test.step('assign a teammate', async () => {
    await card.locator('.card-title').click(); // expand the card
    await expect(card.locator('.collab-sec')).toBeVisible({ timeout: 10_000 });
    await card.locator('select[id^="assign-"]').selectOption({ label: creds.teammate_name });
    await card.getByTitle('Assign').click();
    await expect(card.locator('.dep-chip', { hasText: creds.teammate_name })).toBeVisible({ timeout: 10_000 });
  });

  await test.step('logout via settings', async () => {
    // #user-card now opens the Settings modal (not a bare logout confirm).
    // Log out lives on the Account tab and still confirms + reloads to login.
    await page.locator('#user-card').click();
    await expect(page.locator('#settings-modal')).toBeVisible({ timeout: 10_000 });
    await page.locator('#settings-modal .set-tab', { hasText: 'Account' }).click();
    page.once('dialog', (d) => d.accept());
    await page.locator('#settings-modal').getByRole('button', { name: 'Log out' }).click();
    // Wait for the reload to fully settle before asserting on the fresh DOM.
    await page.waitForURL('**/');
    await page.waitForLoadState('load');
    await expect(page.locator('#wwf-login')).toBeVisible({ timeout: 10_000 });
  });
});
