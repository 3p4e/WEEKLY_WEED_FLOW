// @ts-check
// QMS Studio federation (unification Phase 1): the rail gains a QMS Studio
// zone with the SOP Registry and Knowledge views for elevated roles. The
// local e2e stack deliberately has NO qms-api container, so the proxy's
// graceful "QMS service unavailable" state IS the assertion here — the real
// upstream integration is verified on the wwf_mass test stack.
const { test, expect } = require('@playwright/test');
const { seedOrg, login, gotoModule } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('QMS Studio zone: rail group, both views, graceful unavailable state', async ({ page }) => {
  await login(page, creds.username, creds.password);

  await test.step('the rail shows the QMS Studio group with both views', async () => {
    await gotoModule(page, 'qc');   // QMS Studio + QC views live in the qc module
    await expect(page.locator('.nav-group', { hasText: 'QMS Studio' })).toBeVisible();
    await expect(page.locator('[data-nav="qmsregistry"]')).toBeVisible();
    await expect(page.locator('[data-nav="qmsknow"]')).toBeVisible();
  });

  await test.step('SOP Registry renders with zone banner and the retired state', async () => {
    await page.locator('[data-nav="qmsregistry"]').click();
    await expect(page.locator('.qms-zone')).toBeVisible({ timeout: 10_000 });
    // qms-api is retired platform-wide: its proxy 503 renders as an honest
    // "retired" panel pointing at Document Studio — deliberately NO retry.
    await expect(page.locator('#view-root, main, body').first())
      .toContainText('SOP Registry retired', { timeout: 15_000 });
  });

  await test.step('Knowledge search renders and shows its retired state', async () => {
    await page.locator('[data-nav="qmsknow"]').click();
    await expect(page.locator('#qmsk-q')).toBeVisible({ timeout: 10_000 });
    await page.locator('#qmsk-q').fill('cleaning validation');
    await page.locator('#qmsk-q').press('Enter');
    await expect(page.locator('#view-root, main, body').first())
      .toContainText('Knowledge search retired', { timeout: 15_000 });
  });

  await test.step('Create (DocEngine wizard) renders and degrades gracefully', async () => {
    // no docengine container locally → proxy answers 503 "DocEngine unavailable";
    // the wizard must surface it with a retry, never a blank screen.
    await expect(page.locator('[data-nav="qmsstudio"]')).toBeVisible();
    await page.locator('[data-nav="qmsstudio"]').click();
    await expect(page.locator('#view-root, main, body').first())
      .toContainText('DocEngine unavailable', { timeout: 15_000 });
    await expect(page.getByRole('button', { name: /retry|обиди/i })).toBeVisible();
  });
});
