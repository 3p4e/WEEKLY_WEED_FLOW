// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  // The worklog "weekend session" spec occasionally fails on CI's ephemeral
  // Postgres (a transient the app code is not responsible for — connection
  // handling is context-managed and the classification is deterministic). Two
  // retries absorb that CI-only flakiness; a genuine regression still fails all
  // attempts. Local runs stay at 0 so real failures surface immediately.
  retries: process.env.CI ? 2 : 0,
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
      // 2026-09-07: the self-hosted runner's host was starved by its
      // hypervisor node for most of a day (CPU steal measured 25-93%,
      // /proc/stat), and the backend needed ~65s to answer /health under
      // that load instead of its normal few seconds. 30s was sized for a
      // healthy host and failed the whole job on a live backend that was
      // simply still starting. 180s survives a bad day without masking a
      // truly broken server, which would still exceed it.
      timeout: 180_000,
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
