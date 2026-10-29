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

// get_image_pair maps index 0 to the first *assigned* trial, not the first *uncompleted*
// one, so a participant who reloads after 2 of 4 trials re-answers trial 1.
test.fixme('reloading mid-study resumes on an unserved trial', async ({ page }) => {
  const email = uniqueEmail('resume');
  await startSurvey(page, email);

  const served = [await pairSignature(page)];
  for (let i = 0; i < 2; i++) {
    const before = await pairSignature(page);
    await answerTrial(page);
    await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
    served.push(await pairSignature(page));
  }

  await page.goto('/');
  await expect(page.locator('#survey-section')).toBeVisible();
  const after = await pairSignature(page);
  expect(served, 'resume must not re-serve a completed trial').not.toContain(after);
});
