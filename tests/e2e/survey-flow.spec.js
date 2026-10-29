const { test, expect } = require('@playwright/test');
const { startSurvey, answerTrial, completeSurvey, uniqueEmail, pairSignature } = require('./helpers/survey');
const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);

test('participant completes the whole study in a real browser', async ({ page }) => {
  test.setTimeout(180000);
  await startSurvey(page, uniqueEmail('flow'));

  await expect(page.locator('#total-questions')).not.toHaveText('0');
  await expect(page.locator('#prompt-text')).toContainText('Trial');
  await expect(page.locator('#image-a')).toHaveJSProperty('naturalWidth', 200);
  await expect(page.locator('#image-b')).toHaveJSProperty('naturalWidth', 200);

  let answered = 0;
  while (answered < TRIALS - 1 && !(await page.locator('#mask-image').isVisible())) {
    await answerTrial(page);
    answered++;
  }
  await page.screenshot({ path: 'docs/screenshots/01-survey-trial.png', fullPage: true });

  await completeSurvey(page, TRIALS - answered);
  await page.screenshot({ path: 'docs/screenshots/02-thank-you.png', fullPage: true });
});

// A reload restores the session's assignment, so the server must skip what is already answered
// and report the position inside the study, not restart the counter.
test('the page boots the built bundle, not a source file', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveJSProperty('dataset.build', 'vite');
  await expect(page.locator('script[src*="/dist/assets/survey-"]')).toHaveCount(1);
});

test('reloading mid-study resumes on an unserved trial', async ({ page }) => {
  const email = uniqueEmail('resume');
  await startSurvey(page, email);

  const answered = [];
  for (let i = 0; i < 2; i++) {
    const before = await pairSignature(page);
    await answerTrial(page);
    answered.push(before);
    await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
  }

  await page.goto('/');
  await expect(page.locator('#survey-section')).toBeVisible();
  expect(answered, 'resume must not re-serve an answered trial').not.toContain(await pairSignature(page));
  await expect(page.locator('#current-question')).toHaveText('3');
  await expect(page.locator('#total-questions')).toHaveText(String(TRIALS));
});

