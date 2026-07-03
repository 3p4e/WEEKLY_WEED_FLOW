// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8091',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // This project's pinned @playwright/test version doesn't always match
    // the browser revision pre-cached in this environment's image; point
    // straight at the pre-installed binary instead of letting Playwright
    // look for (and fail to find) its expected revision.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : {},
  },
  // Backend + local nginx proxy (see nginx.local.conf) — same database as
  // the pytest suite (backend/README.md's "Tests" section documents the
  // one-time bootstrap). Each spec seeds its own org via seed_e2e_org.py,
  // same approach as tests/conftest.py's `org` fixture.
  webServer: [
    {
      command: 'bash ../../backend/scripts/run_e2e_backend.sh',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'bash start-nginx.sh',
      url: 'http://127.0.0.1:8091/',
      reuseExistingServer: !process.env.CI,
      timeout: 10_000,
    },
  ],
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
