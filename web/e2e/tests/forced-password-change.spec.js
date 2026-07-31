// @ts-check
const { test, expect } = require('@playwright/test');
const { seedOrg, revealLoginCard } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

test('reloading mid forced-password-change goes back to the change-password screen, not a stuck app', async ({ page, request }) => {
  // Provision a new user via the real API (as the Team UI would) to get a
  // real OTP, without driving the whole admin-side UI flow just for setup.
  const adminLogin = await request.post('/auth/login', { data: { email: creds.username, password: creds.password } });
  expect(adminLogin.ok()).toBeTruthy();
  const adminToken = (await adminLogin.json()).access_token;

  const newUsername = `e2e_pwchange_${Date.now()}`;
  const createRes = await request.post('/auth/users', {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { username: newUsername, full_name: 'PW Change Test', role: 'USER' },
  });
  expect(createRes.ok()).toBeTruthy();
  const otp = (await createRes.json()).otp;

  // Log in with the OTP through the real UI — this persists a token while
  // must_change_password is still true, same as a real first login.
  await revealLoginCard(page);
  await page.locator('#wwf-u').fill(newUsername);
  await page.locator('#wwf-p').fill(otp);
  await page.getByRole('button', { name: 'Authenticate' }).click();
  await expect(page.getByText('Set Passphrase', { exact: true })).toBeVisible({ timeout: 10_000 });

  // Simulate closing the tab before finishing the change: reload with the
  // token already persisted in sessionStorage but must_change_password
  // still true. Before this fix, GF.store.load called loadAndRender()
  // directly, which just 403'd repeatedly behind a toast with no way back.
  await page.reload();
  await expect(page.getByText('Set Passphrase', { exact: true })).toBeVisible({ timeout: 10_000 });

  // The recovered screen must be fully usable, not just visible — finish
  // the change and confirm it lands in the real app.
  await page.locator('#wwf-np').fill('NewPassword123456');
  await page.locator('#wwf-np2').fill('NewPassword123456');
  await page.getByRole('button', { name: 'Set passphrase & continue' }).click();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });
});
