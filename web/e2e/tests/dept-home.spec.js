// @ts-check
// Department home: a department-bound operator lands on their department's
// home screen (fresh browser → role default), quick-add presets render, the
// add modal captures department template fields (room/strain), the created
// task shows attribute chips, and the By-room panel groups it under its room.
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string, operator_username: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('operator lands on department home and creates a room-tagged task', async ({ page }) => {
  const taskTitle = `Watering GR-2 ${Date.now()}`;

  await test.step('login lands on the department home (fresh browser)', async () => {
    await login(page, creds.operator_username, creds.password);
    await expect(page.locator('.dh-head .view-title')).toHaveText(/Cultivation/, { timeout: 10_000 });
    // the nav row exists and is active
    await expect(page.locator('.nav-item.active', { hasText: 'My Department' })).toBeVisible();
    // quick-add preset chips from the cultivation template
    await expect(page.locator('.dh-presets .preset-chip').first()).toBeVisible();
  });

  await test.step('add modal carries the cultivation template fields', async () => {
    await page.locator('#newtask-btn').click();   // header button (the dept-home head has its own)
    await expect(page.locator('#add-dept-fields .af-field')).toHaveCount(3); // room / strain / plant_count
    await page.locator('#add-title').fill(taskTitle);
    await page.locator('#attr-f-room').fill('GR-2');
    await page.locator('#attr-f-strain').fill('Kalorist');
    await page.locator('#attr-f-plant_count').fill('120');
    await page.getByRole('button', { name: 'Create task' }).click();
    // still on dept home — the By-room panel groups the new task under GR-2
    await expect(page.locator('.dh-group-key', { hasText: 'GR-2' })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.dh-group .mw-tcard__title', { hasText: taskTitle })).toBeVisible();
  });

  await test.step('the board card shows the attribute chips', async () => {
    await page.locator('.nav-item', { hasText: 'My Week' }).click();
    const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });
    await expect(card).toBeVisible({ timeout: 10_000 });
    await expect(card.locator('.attr-chip', { hasText: 'GR-2' })).toBeVisible();
    await expect(card.locator('.attr-chip', { hasText: 'Kalorist' })).toBeVisible();
  });

  await test.step('edit round-trips the attributes', async () => {
    const card = page.locator('.card', { has: page.locator('.card-title', { hasText: taskTitle }) });
    await card.locator('.card-title').click();                       // expand
    await card.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('#attr-f-room')).toHaveValue('GR-2');  // prefilled
    await page.locator('#attr-f-room').fill('GR-5');
    await page.getByRole('button', { name: /save/i }).click();
    await expect(card.locator('.attr-chip', { hasText: 'GR-5' })).toBeVisible({ timeout: 10_000 });
  });
});
