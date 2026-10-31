const { test, expect } = require('@playwright/test');
const { answerVisibleGroups, startSurvey } = require('./helpers/survey');
const { startShotServer } = require('./helpers/screens');

const PORT = 5076;
const EMAIL = 'e2e-tutorial@example.com';

// The walkthrough is where the component tree and script.js must agree: the banner is a component, Submit is script.js.
test('the tutorial walkthrough walks its steps and then unlocks the form', async ({ browser }) => {
  test.setTimeout(240000);
  const server = await startShotServer(PORT);
  const context = await browser.newContext({ baseURL: server.base, viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const banner = page.locator('#tutorial-banner');
  const submitBtn = page.locator('#submit-btn');

  try {
    await startSurvey(page, EMAIL);
    // /tutorial gates on the session's referral_validated flag, which /referral sets (and which
    // index() only checks when referrals are required). Without this hop the tutorial is 302.
    await page.goto('/referral');
    await page.goto('/tutorial');

    await expect(banner).toBeVisible();
    const firstTitle = await page.locator('#tutorial-title').textContent();
    expect(firstTitle.trim().length).toBeGreaterThan(0);
    await expect(submitBtn).toBeDisabled();
    await expect(submitBtn).toHaveAttribute('title', 'Complete the tutorial first');

    const steps = [];
    let mostHighlights = 0;
    // A runaway-loop guard, not a step count: the steps come from the fixture's config.
    for (let i = 0; i < 24 && await banner.isVisible(); i += 1) {
      steps.push((await page.locator('#tutorial-title').textContent()).trim());
      mostHighlights = Math.max(mostHighlights, await page.locator('.tutorial-highlight').count());
      await page.locator('.btn-tutorial-primary').click();
    }
    expect(steps.length).toBeGreaterThan(1);
    expect(new Set(steps).size).toBe(steps.length);
    // Steps without a highlight are legal; a walkthrough that never points at anything is not.
    expect(mostHighlights).toBeGreaterThan(0);
    await expect(banner).toBeHidden();

    await expect(submitBtn).toBeDisabled();
    await answerVisibleGroups(page);
    await expect(submitBtn).toBeEnabled();

    const tutorialCalls = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/complete_tutorial')) tutorialCalls.push(request.method());
    });
    const postedResponses = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/submit_survey')) postedResponses.push(request.url());
    });

    await submitBtn.click();
    await page.waitForURL(`${server.base}/`);
    expect(tutorialCalls).toEqual(['POST']);
    expect(postedResponses).toEqual([]);
    expect(pageErrors).toEqual([]);
  } finally {
    await context.close();
    server.stop();
  }
});
