const { defineConfig, devices } = require('@playwright/test');

const PORT = process.env.E2E_PORT || '5055';
const BASE = `http://127.0.0.1:${PORT}`;

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
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, testIgnore: /mobile.*\.spec\.js/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testMatch: /mobile.*\.spec\.js/ },
  ],
  webServer: {
    command: 'bash tests/e2e/fixture/server.sh',
    url: `${BASE}/health`,
    env: { PORT },
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
