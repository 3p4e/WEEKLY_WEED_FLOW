// @ts-check
const { test, expect } = require('@playwright/test');
const { seedOrg } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('estimated hours at creation + hours-spent on the card persist across a reload', async ({ page }) => {
  const taskTitle = `Effort task ${Date.now()}`;

  await page.goto('/');
  await page.locator('#wwf-u').fill(creds.username);
  await page.locator('#wwf-p').fill(creds.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });

  await test.step('create a task with an estimate', async () => {
    await page.getByRole('button', { name: /new task/i }).click();
    await page.locator('#add-title').fill(taskTitle);
    await page.locator('#add-est').fill('4');
    await page.getByRole('button', { name: 'Create task' }).click();
    await expect(page.locator('.card-title', { hasText: taskTitle })).toBeVisible({ timeout: 10_000 });
  });

  const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });

  await test.step('log hours spent on the expanded card', async () => {
    await card.locator('.card-title').click();               // expand
    const hrs = card.locator('input[id^="hrs-"]');
    await expect(hrs).toBeVisible({ timeout: 10_000 });
    await expect(hrs).toHaveValue('');                        // no actual hours yet
    await hrs.fill('5.5');
    await hrs.blur();                                          // onchange → PATCH
    // The estimate shows next to it ("/ est 4").
    await expect(card).toContainText('4');
  });

  await test.step('reload — the logged hours came from the backend, not local state', async () => {
    await page.reload();
    await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });
    const card2 = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });
    await card2.locator('.card-title').click();               // expand the fresh card
    await expect(card2.locator('input[id^="hrs-"]')).toHaveValue('5.5', { timeout: 10_000 });
  });
});
