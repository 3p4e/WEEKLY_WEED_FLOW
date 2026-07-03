// @ts-check
const { test, expect } = require('@playwright/test');
const { seedOrg } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('roll over persists across a reload instead of silently reverting', async ({ page }) => {
  const taskTitle = `Rollover test ${Date.now()}`;

  await page.goto('/');
  await page.locator('#wwf-u').fill(creds.username);
  await page.locator('#wwf-p').fill(creds.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });

  await page.getByRole('button', { name: /new task/i }).click();
  await page.locator('#add-title').fill(taskTitle);
  await page.getByRole('button', { name: 'Create task' }).click();
  const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });
  await expect(card).toBeVisible({ timeout: 10_000 });

  await page.getByRole('button', { name: 'Roll over' }).click();
  // The task must leave the current week's panel immediately...
  await expect(card).toBeHidden({ timeout: 10_000 });

  // ...and — the actual bug this pins — still be gone after a reload,
  // instead of reverting because the old rollover only mutated in-memory
  // state and called a no-op GF.store.save().
  await page.reload();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });
  await expect(page.locator('.card-title', { hasText: taskTitle })).toBeHidden({ timeout: 10_000 });

  // It really moved forward, not just vanished: next week must have it.
  await page.locator('#week-strip .icon-btn').nth(1).click();
  await expect(page.locator('.card-title', { hasText: taskTitle })).toBeVisible({ timeout: 10_000 });
});
