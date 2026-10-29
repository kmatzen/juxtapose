const { test, expect } = require('@playwright/test');

const PASSWORD = process.env.ADMIN_PASSWORD || 'e2e-admin-password';
const STATE = 'test-results/admin-auth.json';

// One admin sign-in per run: /admin/login is IP-keyed at 10/hour, and every dashboard test
// logging in burns that budget on the shared 127.0.0.1 the fixture server sees.
test('sign in as admin', async ({ page }) => {
  await page.goto('/admin/login');
  await page.fill('#password', PASSWORD);
  await page.locator('form').evaluate((f) => f.submit());
  await expect(page).toHaveURL(/\/admin$/);
  await page.context().storageState({ path: STATE });
});
