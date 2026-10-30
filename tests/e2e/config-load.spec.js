const { test, expect } = require('@playwright/test');
const { uniqueEmail, submitDemographics } = require('./helpers/survey');

// /api/config gates runner.start() and builds the questions, so a page that gives up quietly shows a form that can never submit.
test('a study config that fails says so on the page and asks the server again', async ({ page }) => {
  test.setTimeout(120000);
  const attempts = [];
  await page.route('**/api/config', async (route) => {
    attempts.push(route.request().url());
    if (attempts.length === 1) {
      await route.abort('failed');
      return;
    }
    await route.continue();
  });

  await page.goto('/');
  await expect(page.locator('#demographics-section')).toBeVisible();
  await expect(page.locator('.error-message').first())
    .toContainText('Failed to load the study setup');
  await expect.poll(() => attempts.length, { timeout: 15000 }).toBeGreaterThanOrEqual(2);

  // The recovered read clears the warning: a stale failure banner over a working study is a lie.
  await expect(page.locator('.error-message')).toBeHidden({ timeout: 15000 });

  await submitDemographics(page, uniqueEmail('config'));
  await expect(page.locator('#survey-section')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#survey-form .evaluation-section').first()).toBeVisible();
});
