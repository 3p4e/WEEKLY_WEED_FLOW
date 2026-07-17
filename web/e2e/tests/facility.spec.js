// @ts-check
// Facility board (the owner's ask): an elevated user opens Facility from the
// Operations rail group, an admin-seeded grow room renders, a batch is added
// through the room modal (strain / count / phase choosers), and the room cell
// + phase KPI totals reflect it.
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('facility board: room renders, batch added, totals update', async ({ page }) => {
  await login(page, creds.username, creds.password);

  await test.step('seed a grow room through the ADMIN API', async () => {
    await page.evaluate(() => window['GF'].API.facilityAddRoom(
      { code: 'grow_e2e', name: 'Grow Room 1', name_mk: 'Сала 1', kind: 'flower' }));
  });

  await test.step('open Facility from the rail', async () => {
    await page.locator('.nav-item', { hasText: 'Facility' }).click();
    await expect(page.locator('.view-title', { hasText: 'Facility' })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.fac-room .fr-nm', { hasText: 'Grow Room 1' })).toBeVisible({ timeout: 10_000 });
  });

  await test.step('add a batch via the room modal', async () => {
    await page.locator('.fac-room', { has: page.locator('.fr-nm', { hasText: 'Grow Room 1' }) }).click();
    const room = page.locator('#fac-room-modal');
    await expect(room).toBeVisible();
    await room.getByRole('button', { name: /add batch/i }).click();
    const modal = page.locator('#fac-batch-modal');
    await expect(modal).toBeVisible();
    await modal.locator('#fb-strain').fill('Gorilla Glue');
    await modal.locator('#fb-count').fill('96');
    await modal.locator('#fb-phase-btn').click();                    // phase chooser
    await page.locator('#gf-chooser .sel-row[data-v="flower"]').click();
    await modal.getByRole('button', { name: /save|зачувај/i }).click();
  });

  await test.step('room cell and phase totals reflect the batch', async () => {
    const cell = page.locator('.fac-room', { has: page.locator('.fr-nm', { hasText: 'Grow Room 1' }) });
    await expect(cell.locator('.fr-n')).toHaveText('96', { timeout: 10_000 });
    await expect(cell.locator('.fs-nm', { hasText: 'Gorilla Glue' })).toBeVisible();
    // the Flowering resource-strip readout counts it (the totals row renders
    // as .fac-res entries — icon + glowing count — not .kpi tiles)
    const res = page.locator('.fac-res', { has: page.locator('.fac-res-l', { hasText: /flowering/i }) });
    await expect(res.locator('.fac-res-v')).toHaveText('96');
  });
});
