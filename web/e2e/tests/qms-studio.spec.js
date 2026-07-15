// @ts-check
// QMS Studio federation (unification Phase 1): the rail gains a QMS Studio
// zone with the SOP Registry and Knowledge views for elevated roles. The
// local e2e stack deliberately has NO qms-api container, so the proxy's
// graceful "QMS service unavailable" state IS the assertion here — the real
// upstream integration is verified on the wwf_mass test stack.
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('QMS Studio zone: rail group, both views, graceful unavailable state', async ({ page }) => {
  await login(page, creds.username, creds.password);

  await test.step('the rail shows the QMS Studio group with both views', async () => {
    await expect(page.locator('.nav-group', { hasText: 'QMS Studio' })).toBeVisible();
    await expect(page.locator('[data-nav="qmsregistry"]')).toBeVisible();
    await expect(page.locator('[data-nav="qmsknow"]')).toBeVisible();
  });

  await test.step('SOP Registry renders with zone banner and the unavailable state', async () => {
    await page.locator('[data-nav="qmsregistry"]').click();
    await expect(page.locator('.qms-zone')).toBeVisible({ timeout: 10_000 });
    // no qms-api locally → proxy answers 503 with this exact detail string
    await expect(page.locator('#view-root, main, body').first())
      .toContainText('QMS service unavailable', { timeout: 15_000 });
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();
  });

  await test.step('Knowledge search renders and degrades the same way', async () => {
    await page.locator('[data-nav="qmsknow"]').click();
    await expect(page.locator('#qmsk-q')).toBeVisible({ timeout: 10_000 });
    await page.locator('#qmsk-q').fill('cleaning validation');
    await page.locator('#qmsk-q').press('Enter');
    await expect(page.locator('#view-root, main, body').first())
      .toContainText('QMS service unavailable', { timeout: 15_000 });
  });
});
