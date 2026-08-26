// @ts-check
// Facility board (the owner's ask): an elevated user opens Facility from the
// Operations rail group, an admin-seeded grow room renders, a batch created
// through the Cultivation board (POST /cultivation/batches) shows up on the
// read-only Facility board, and the room cell + phase totals reflect it.
//
// NOTE: prior to the 2026-08 audit's Critical fix, batches could ALSO be
// added/edited/closed directly from the Facility room modal — a second,
// unaudited write path onto the same plant_batches rows the Cultivation
// board owns, which crashed the whole board for any phase value the
// facility-side totals map hadn't hardcoded. That duplicate write path
// (facility-view.js's openBatch/saveBatch/closeBatch, and the backend's
// POST/PATCH /facility/batches) was removed entirely — Facility is now
// read-only over batches, sourced live from Cultivation's own writes. This
// spec was updated to match: it seeds the batch via the real (sole) write
// path and asserts the Facility board's read-only room modal reflects it,
// with no add/edit affordance left to click.
const { test, expect } = require('@playwright/test');
const { seedOrg, login, gotoModule } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('facility board: room renders, a Cultivation-created batch shows read-only, totals update', async ({ page }) => {
  await login(page, creds.username, creds.password);

  /** @type {{id: string}} */
  let room;
  /** @type {{id: string}} */
  let cultivar;

  await test.step('seed a grow room and a cultivar through the ADMIN API', async () => {
    room = await page.evaluate(() => window['GF'].API.facilityAddRoom(
      { code: 'grow_e2e', name: 'Grow Room 1', name_mk: 'Сала 1', kind: 'flower' }));
    cultivar = await page.evaluate(() => window['GF'].API.cultivarCreate(
      { code: 'gg_e2e', name: 'Gorilla Glue', name_mk: 'Горила Глу' }));
  });

  await test.step('seed a batch through the Cultivation board — the sole write path', async () => {
    await page.evaluate(([roomId, cultivarId]) => window['GF'].API.cultivationBatchCreate({
      room_id: roomId, cultivar_id: cultivarId, code: 'gg-e2e-1',
      plant_count: 96, phase: 'flower',
    }), [room.id, cultivar.id]);
  });

  await test.step('open Facility from the rail', async () => {
    await gotoModule(page, 'cultivation');   // Facility lives in the cultivation module
    await page.locator('.nav-item', { hasText: 'Facility' }).click();
    await expect(page.locator('.view-title', { hasText: 'Facility' })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.fac-room .fr-nm', { hasText: 'Grow Room 1' })).toBeVisible({ timeout: 10_000 });
  });

  await test.step('room cell and phase totals reflect the Cultivation-created batch', async () => {
    const cell = page.locator('.fac-room', { has: page.locator('.fr-nm', { hasText: 'Grow Room 1' }) });
    await expect(cell.locator('.fr-n')).toHaveText('96', { timeout: 10_000 });
    await expect(cell.locator('.fs-nm', { hasText: 'Gorilla Glue' })).toBeVisible();
    // the Flowering resource-strip readout counts it (the totals row renders
    // as .fac-res entries — icon + glowing count — not .kpi tiles)
    const res = page.locator('.fac-res', { has: page.locator('.fac-res-l', { hasText: /flowering/i }) });
    await expect(res.locator('.fac-res-v')).toHaveText('96');
  });

  await test.step('the room modal shows the batch read-only, with no edit affordance', async () => {
    await page.locator('.fac-room', { has: page.locator('.fr-nm', { hasText: 'Grow Room 1' }) }).click();
    const modal = page.locator('#fac-room-modal');
    await expect(modal).toBeVisible();
    await expect(modal.getByText('Gorilla Glue')).toBeVisible();
    await expect(modal.getByText('96')).toBeVisible();
    // no batch-editing affordance survives in this modal — the duplicate
    // write path was removed, not merely hidden behind a role gate
    await expect(modal.getByRole('button', { name: /add batch/i })).toHaveCount(0);
    await expect(modal.getByText(/cultivation board/i)).toBeVisible();
  });
});
