// @ts-check
// Executive Report view: submission-status chips reflect compile state, the
// org-wide section expands to task drill-down with note authors, the deep
// link lands on the expanded board card, and the standalone interactive HTML
// export actually downloads. Documents are compiled through the app's own
// authenticated API client (page.evaluate) — the authoring UI has its own
// spec coverage; this one tests CONSUMPTION.
const { test, expect } = require('@playwright/test');
const { seedOrg, login, gotoModule } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('executive report: status board, drill-down, deep link, HTML export', async ({ page }) => {
  const taskTitle = `XR drill task ${Date.now()}`;

  await test.step('login and seed a task + note + compiled org document', async () => {
    await login(page, creds.username, creds.password);
    await page.evaluate(async (title) => {
      // Drive the real API with the session's own token — GF.API is the
      // app's authenticated client.
      const t = await GF.API.createTask({ title, status: 'ongoing', priority: 'high' });
      await GF.API.addProgress(t.id, { day_label: 'Mon', note: 'Executive drill-down note.' });
      await GF.API.compileDocument({ kind: 'report' });
    }, taskTitle);
  });

  await test.step('open the Executive Report view — org chip shows draft', async () => {
    await gotoModule(page, 'analytics');   // Executive Report lives in the analytics module
    await page.locator('.nav-item', { hasText: 'Executive Report' }).click();
    await expect(page.locator('.xr-chips .xr-chip-in', { hasText: 'Org-wide' })).toBeVisible({ timeout: 10_000 });
    // one department chip (cultivation) still missing, org-wide is a draft
    const orgSection = page.locator('.xr-sec', { hasText: 'Org-wide' });
    await expect(orgSection.locator('.xr-chip-in', { hasText: 'Draft' })).toBeVisible();
    await expect(page.locator('.xr-sec', { hasText: 'Cultivation' }).locator('.xr-chip-in', { hasText: 'Missing' })).toBeVisible();
  });

  const orgSection = page.locator('.xr-sec', { hasText: 'Org-wide' });

  await test.step('expand org section → task row with note author', async () => {
    await orgSection.locator('.xr-sec-head').click();
    const task = orgSection.locator('.xr-task', { hasText: taskTitle });
    await expect(task).toBeVisible({ timeout: 10_000 });
    await task.locator('summary').click();
    await expect(task.locator('.xr-note', { hasText: 'Executive drill-down note.' })).toBeVisible();
    await expect(task.locator('.xr-note .by', { hasText: 'E2E Admin' })).toBeVisible();
  });

  await test.step('deep link lands on the expanded board card', async () => {
    await orgSection.locator('.xr-task', { hasText: taskTitle })
      .getByRole('button', { name: /open in board/i }).click();
    const card = page.locator('.card.expanded', { has: page.locator('.card-title', { hasText: taskTitle }) });
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  await test.step('standalone interactive HTML downloads', async () => {
    // The deep-link step above followed "Open in board" back into the tasks
    // module (setView is module-aware now); return to analytics for the export.
    await gotoModule(page, 'analytics');
    await page.locator('.nav-item', { hasText: 'Executive Report' }).click();
    const sec = page.locator('.xr-sec', { hasText: 'Org-wide' });
    if (!(await sec.locator('.xr-exports').isVisible())) await sec.locator('.xr-sec-head').click();
    const downloadP = page.waitForEvent('download');
    await sec.getByRole('button', { name: /interactive html/i }).click();
    const download = await downloadP;
    expect(download.suggestedFilename()).toMatch(/^wwf-report-\d{4}-\d{2}-\d{2}.*\.html$/);
  });
});
