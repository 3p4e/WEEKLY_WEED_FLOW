// @ts-check
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

/** Saturday of the Fri→Thu report window containing today, as YYYY-MM-DD
 *  (local time — the backend classifies session timestamps as facility
 *  wall-clock, and /reports/weekly windows on the server's date.today()). */
function windowSaturday() {
  const now = new Date();
  const daysSinceFri = (now.getDay() - 5 + 7) % 7; // JS: Sun=0 … Sat=6
  const sat = new Date(now);
  sat.setDate(now.getDate() - daysSinceFri + 1);
  const p = (n) => String(n).padStart(2, '0');
  return `${sat.getFullYear()}-${p(sat.getMonth() + 1)}-${p(sat.getDate())}`;
}

test('due date + type at creation, weekend session logged; report renders WITHOUT hour metrics', async ({ page }) => {
  const taskTitle = `Worklog task ${Date.now()}`;
  const sat = windowSaturday();

  await login(page, creds.username, creds.password);

  await test.step('create a task with a due date and a type', async () => {
    await page.getByRole('button', { name: /new task/i }).click();
    await page.locator('#add-title').fill(taskTitle);
    await page.locator('#add-due').fill(sat);
    // task type is a popup chooser (chooser.js), not a native <select>
    await page.locator('#add-type-btn').click();
    await page.locator('#gf-chooser .sel-row[data-v="lab"]').click();
    await page.getByRole('button', { name: 'Create task' }).click();
    await expect(page.locator('.card-title', { hasText: taskTitle })).toBeVisible({ timeout: 10_000 });
  });

  const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });

  await test.step('the card carries the new badges', async () => {
    await expect(card.locator('.due-badge')).toContainText(sat);
    await expect(card.locator('.type-chip')).toContainText(/lab/i);
  });

  await test.step('log a Saturday work session — classified as weekend', async () => {
    await card.locator('.card-title').click();               // expand
    await card.getByRole('button', { name: /log work/i }).click();
    const modal = page.locator('#worklog-modal');
    await expect(modal).toBeVisible();
    await modal.locator('#wl-date').fill(sat);
    await modal.locator('#wl-start').fill('10:00');
    await modal.locator('#wl-hours').fill('2.5');
    await modal.locator('.modal-body').getByRole('button', { name: /log work/i }).click();
    // Assert the DURABLE outcome — the persisted session row re-rendered from the
    // API response, carrying its classification chip — rather than the success
    // toast. The toast auto-dismisses after ~3s (core.js), so under CI load it's a
    // flaky signal; the row proves the same thing (session logged AND classified
    // "weekend") but stays in the DOM until the modal closes.
    await expect(modal.locator('.sess-class.weekend')).toBeVisible({ timeout: 15_000 });
    await modal.locator('.btn-ghost').click();               // close the modal
  });

  await test.step('set completion % from the worklog panel', async () => {
    await card.getByRole('button', { name: /log work/i }).click();
    const modal = page.locator('#worklog-modal');
    await expect(modal).toBeVisible();
    // quick-set 75% → persists (PATCH progress) and re-renders with the value
    await modal.locator('.pl-q', { hasText: '75%' }).click();
    await expect(modal.locator('#wl-pct-val')).toHaveText('75%', { timeout: 15_000 });
    await expect(modal.locator('.pl-q.on')).toHaveText('75%');
    // 100% surfaces the never-enforced "mark done?" suggestion
    await modal.locator('.pl-q', { hasText: '100%' }).click();
    await expect(modal.locator('.subdone-hint')).toBeVisible({ timeout: 15_000 });
    await modal.locator('.btn-ghost').click();
    // the card's completion bar now reads the explicit percent
    await expect(card.locator('.card-actions .mono')).toHaveText('100%');
  });

  await test.step('the report view renders and the hours table is GONE (removed app-wide)', async () => {
    await page.locator('[data-nav="report"]').click();
    // the report body renders (activity band region or summary cards present)
    await expect(page.locator('#report-view')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('#report-view')).toContainText(taskTitle, { timeout: 15_000 });
    // the per-person hours table was removed with the rest of the hour metrics
    await expect(page.locator('#report-hours')).toHaveCount(0);
  });
});
