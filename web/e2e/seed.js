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
    DATABASE_URL: process.env.DATABASE_URL || 'postgresql://app_user:testpw_user@localhost:5432/weekly_weed_flow_test',
    ADMIN_DATABASE_URL: process.env.ADMIN_DATABASE_URL || 'postgresql://app_admin:testpw_admin@localhost:5432/weekly_weed_flow_test',
  };
  const out = execFileSync(
    path.join(backendDir, '.venv', 'bin', 'python'),
    [path.join(backendDir, 'scripts', 'seed_e2e_org.py')],
    { env, encoding: 'utf-8' },
  );
  return JSON.parse(out.trim().split('\n').pop());
}

module.exports = { seedOrg };
