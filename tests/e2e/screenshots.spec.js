const { test, expect } = require('@playwright/test');
const { startSurvey, completeSurvey, submitDemographics } = require('./helpers/survey');
const { startShotServer, pinRandom, shot, PASSWORD } = require('./helpers/screens');

const PORT = 5071;
const EMAIL = 'shot-participant@example.com';

// The docs/screenshots images are committed, so a reviewer sees them change in a diff. They are
// taken here, from a one-row study with fixed emails, instead of from the behavioural specs
// whose per-session shuffle and timestamped emails make every run's pixels differ.
test('the committed desktop screenshots come from one deterministic study', async ({ browser }) => {
  test.setTimeout(300000);
  const server = await startShotServer(PORT);
  const context = await browser.newContext({ baseURL: server.base, viewport: { width: 1280, height: 900 } });
  await pinRandom(context);
  const page = await context.newPage();
  // time_spent is a real elapsed measure, so freeze the clock and spend a fixed 4.2s per trial.
  await page.clock.install({ time: new Date('2026-03-01T09:00:00Z') });

  try {
    await startSurvey(page, EMAIL);
    await shot(page, '01-survey-trial');

    await page.locator('#identity-images .identity-image').first().hover();
    await expect(page.locator('canvas.mask-overlay')).toHaveCount(2);
    await shot(page, '03-mask-overlay-hover');
    await page.mouse.move(0, 0);

    await page.clock.runFor(4200);
    await completeSurvey(page, 1);
    await shot(page, '02-thank-you');

    // A returning email in a session that has not taken the study is what raises the warning.
    const returning = await browser.newContext({ baseURL: server.base, viewport: { width: 1280, height: 900 } });
    await pinRandom(returning);
    const pageB = await returning.newPage();
    await submitDemographics(pageB, EMAIL);
    await expect(pageB.locator('#retake-modal')).toBeVisible();
    // Viewport, not fullPage: the backdrop is fixed to the viewport, so a taller capture
    // would show undimmed page below the fold that a participant never sees.
    await shot(pageB, '04-retake-modal', { fullPage: false });
    await returning.close();

    const admin = await context.newPage();
    await admin.clock.install({ time: new Date('2026-03-01T09:00:00Z') });
    await admin.goto('/admin/login');
    await admin.fill('#password', PASSWORD);
    await admin.locator('form').evaluate((f) => f.submit());
    await expect(admin).toHaveURL(/\/admin$/);
    await admin.locator('#results-table th').first().waitFor();
    await admin.locator('#toggle-view').click();
    await expect(admin.locator('#view-mode')).toHaveText('Responses View');
    await shot(admin, '05-admin-dashboard');
    await admin.close();
  } finally {
    await context.close();
    server.stop();
  }
});
