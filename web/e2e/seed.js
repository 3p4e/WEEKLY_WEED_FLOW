// Seeds a fresh org + ADMIN account for one spec file by shelling out to the
// same Python bootstrap the pytest suite uses (backend/scripts/seed_e2e_org.py)
// — the app has no self-signup, so e2e tests need a real account to log in
// as before they can drive anything else.
const { execFileSync } = require('child_process');
const path = require('path');

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

module.exports = { seedOrg };
