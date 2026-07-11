// Seeds a fresh org + ADMIN account for one spec file by shelling out to the
// same Python bootstrap the pytest suite uses (backend/scripts/seed_e2e_org.py)
// — the app has no self-signup, so e2e tests need a real account to log in
// as before they can drive anything else.
const { execFileSync } = require('child_process');
const path = require('path');
const { expect } = require('@playwright/test');

function seedOrg() {
  const backendDir = path.join(__dirname, '..', '..', 'backend');
  const env = {
    ...process.env,
    // Two databases in the v2 split (identity vs work) — defaults must match
    // backend/scripts/run_e2e_backend.sh.
    USERS_ADMIN_DATABASE_URL: process.env.USERS_ADMIN_DATABASE_URL || 'postgresql://app_admin:testpw_admin@localhost:5432/wwf_users_test',
    TASKS_ADMIN_DATABASE_URL: process.env.TASKS_ADMIN_DATABASE_URL || 'postgresql://app_admin:testpw_admin@localhost:5432/wwf_tasks_test',
  };
  const out = execFileSync(
    path.join(backendDir, '.venv', 'bin', 'python'),
    [path.join(backendDir, 'scripts', 'seed_e2e_org.py')],
    { env, encoding: 'utf-8' },
  );
  return JSON.parse(out.trim().split('\n').pop());
}

// Reveal the splash's sign-in card. The stage's CLICK handler is bound
// asynchronously (the 3D-leaf mount fetches an OBJ / initializes WebGL before
// wiring onEnter), so a too-early tap can land on a stage with no handler and
// the card never reveals — the old inline boilerplate raced this and could
// hang on slow/first-load environments. The stage's KEYDOWN (Enter/Space)
// handler IS bound synchronously in buildEntry, so fall back to pressing
// Enter until the card is actually visible.
async function revealLoginCard(page) {
  // Hermetic e2e: the app's ONLY external origin is Google Fonts (decorative
  // @import in app.css). In sandboxed/offline environments that fetch can
  // stall for tens of seconds and hold the page 'load' event hostage — which
  // goto() and every post-logout reload wait on. Abort it deterministically;
  // the route persists across reloads for this page.
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/, (r) => r.abort());
  await page.goto('/');
  const stage = page.locator('#gf-leaf-stage');
  const user = page.locator('#wwf-u');
  await stage.click();
  for (let i = 0; i < 20 && !(await user.isVisible()); i++) {
    await stage.press('Enter').catch(() => {});
    await page.waitForTimeout(400);
  }
  await expect(user).toBeVisible({ timeout: 5_000 });
}

// Shared happy-path login: splash → sign-in card → app shell. Every spec that
// signs in normally uses this; forced-password-change keeps its own inline
// flow AFTER the reveal because it asserts the intermediate change-password
// screen instead of the shell.
async function login(page, username, password) {
  await revealLoginCard(page);
  await page.locator('#wwf-u').fill(username);
  await page.locator('#wwf-p').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#wwf-login')).toBeHidden({ timeout: 15_000 });
}

module.exports = { seedOrg, login, revealLoginCard };
