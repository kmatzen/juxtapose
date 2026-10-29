const { defineConfig, devices } = require('@playwright/test');

const PORT = process.env.E2E_PORT || '5055';
const BASE = `http://127.0.0.1:${PORT}`;
const ADMIN_STATE = 'test-results/admin-auth.json';

module.exports = defineConfig({
  testDir: './tests/e2e',
  outputDir: 'test-results',
  timeout: 60000,
  expect: { timeout: 10000 },
  // One fixture database: parallel workers would race on the study's participant rows.
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: BASE,
    viewport: { width: 1280, height: 900 },
    actionTimeout: 8000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'auth', testMatch: /auth\.setup\.js/ },
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], storageState: ADMIN_STATE },
      testIgnore: [/mobile.*\.spec\.js/, /auth\.setup\.js/],
      dependencies: ['auth'],
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'], storageState: ADMIN_STATE },
      testMatch: /mobile.*\.spec\.js/,
      dependencies: ['auth'],
    },
  ],
  webServer: {
    // Building here means any entry point (npx playwright test, npm run test:e2e, CI) tests
    // current assets; a stale static_dist silently serves the page the test did not write.
    command: 'npm run build --silent && bash tests/e2e/fixture/server.sh',
    url: `${BASE}/health`,
    env: { PORT },
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
