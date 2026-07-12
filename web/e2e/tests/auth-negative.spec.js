// @ts-check
// Negative-path auth coverage: the suite's other specs all sign in
// successfully — nothing pinned what a REJECTED login looks like. This spec
// asserts a wrong password (a) surfaces a visible error, (b) never reveals
// the app shell, and (c) does not poison the account: the right password
// still works immediately afterwards (the login rate limiter counts failures,
// one typo must not lock the user out).
const { test, expect } = require('@playwright/test');
const { seedOrg, login, revealLoginCard } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('wrong password is rejected visibly and does not lock out the real one', async ({ page }) => {
  await revealLoginCard(page);
  await page.locator('#wwf-u').fill(creds.username);
  await page.locator('#wwf-p').fill('definitely-not-the-password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  // The login card must stay up with a visible error. (The app scaffold
  // renders in the DOM behind the overlay even pre-login, so asserting on
  // shell elements would false-positive — the overlay staying up IS the
  // meaningful check.)
  await expect(page.locator('#wwf-login')).toBeVisible();
  await expect(page.locator('#wwf-login')).toContainText(/invalid|погрешн|incorrect|failed|неуспе/i,
    { timeout: 10_000 });

  // Same page, correct credentials — must succeed (failure counter, not a lock).
  await page.locator('#wwf-p').fill(creds.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });
});

test('unknown username is rejected the same way (no account enumeration hint)', async ({ page }) => {
  await revealLoginCard(page);
  await page.locator('#wwf-u').fill(`ghost_${Date.now()}`);
  await page.locator('#wwf-p').fill('whatever-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#wwf-login')).toBeVisible();
  await expect(page.locator('#wwf-login')).toContainText(/invalid|погрешн|incorrect|failed|неуспе/i,
    { timeout: 10_000 });
});
