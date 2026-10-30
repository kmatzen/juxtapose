const { test, expect } = require('@playwright/test');
const {
  startSurvey, submitDemographics, answerTrial, completeSurvey, uniqueEmail,
} = require('./helpers/survey');
const { startShotServer } = require('./helpers/screens');

const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);
const ROWS = 6;
const CAP = 4;
const ANSWERED_BEFORE = 2;
const OWED = CAP - ANSWERED_BEFORE;
const SIDE_SERVER_PORT = 5195;

// Fifth audit, findings 2 and 4: both shipped green because the unit tiers cannot see them. The
// backend suite ran with CSRF off, and the resumed-budget test ignored the completed flag the
// client navigates on. This file drives the pages a participant drives, with CSRF on.
test('Start Over clears the session when CSRF protection is on', async ({ page }) => {
  await startSurvey(page, uniqueEmail('startover'));
  await completeSurvey(page, TRIALS);

  await page.getByRole('link', { name: 'Start Over' }).click();
  await expect(page.locator('.reset-box')).toBeVisible();
  await page.locator('.btn-reset').click();

  await expect(page).not.toHaveURL(/reset_session_confirm$/, { timeout: 15000 });
  await expect(page.locator('#demographics-section')).toBeVisible({ timeout: 15000 });
});

test('a returning participant is served the trials they still owe', async ({ browser }) => {
  test.setTimeout(240000);
  // The fixture's rows must outnumber the per-user cap: with rows equal to the cap the min() in the
  // assignment hides the budget and this spec is green before the fix.
  const server = await startShotServer(SIDE_SERVER_PORT,
    { rows: String(ROWS), pairsPerUser: CAP, seed: null });
  const email = uniqueEmail('resume');

  try {
    const first = await browser.newContext({ baseURL: server.base });
    const pageA = await first.newPage();
    await startSurvey(pageA, email);
    for (let i = 0; i < ANSWERED_BEFORE; i++) {
      await answerTrial(pageA);
    }
    await first.close();

    const second = await browser.newContext({ baseURL: server.base });
    const pageB = await second.newPage();
    await submitDemographics(pageB, email);
    await expect(pageB.locator('#retake-modal')).toBeVisible();
    await pageB.locator('#retake-cancel').click();
    await expect(pageB.locator('#survey-section')).toBeVisible({ timeout: 15000 });

    await expect(pageB.locator('#total-questions'),
      'the resumed session must promise what it will serve, not the study cap').toHaveText(`${OWED}`);
    await completeSurvey(pageB, OWED);
    await second.close();
  } finally {
    server.stop();
  }
});
