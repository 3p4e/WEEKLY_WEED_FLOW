// @ts-check
// QMS Studio federation (unification Phase 1): the rail gains a QMS Studio
// zone for elevated roles, holding Document Studio (DocEngine-backed) and the
// QC LIMS views. The legacy SOP Registry and Knowledge Search views — stubs
// that only ever printed "retired" after qms-api was withdrawn platform-wide —
// were removed from the shell on 2026-09-27 (review FE-21), so the zone is
// asserted through the views that still live in it. The local e2e stack
// deliberately has NO docengine container, so the proxy's graceful
// "DocEngine unavailable" state IS the assertion here.
const { test, expect } = require('@playwright/test');
const { seedOrg, login, gotoModule } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('QMS Studio zone: rail group, Document Studio, graceful unavailable state', async ({ page }) => {
  await login(page, creds.username, creds.password);

  await test.step('the rail shows the QMS Studio group, without the retired views', async () => {
    await gotoModule(page, 'qc');   // QMS Studio + QC views live in the qc module
    await expect(page.locator('.nav-group', { hasText: 'QMS Studio' })).toBeVisible();
    await expect(page.locator('[data-nav="qmsstudio"]')).toBeVisible();
    await expect(page.locator('[data-nav="qmsregistry"]')).toHaveCount(0);
    await expect(page.locator('[data-nav="qmsknow"]')).toHaveCount(0);
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
