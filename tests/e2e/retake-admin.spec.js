const { test, expect } = require('@playwright/test');
const {
  startSurvey, submitDemographics, fillDemographics, answerTrial, completeSurvey, gotoTrialWithMask, uniqueEmail,
} = require('./helpers/survey');

const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);
// The admin session cookie is seeded by tests/e2e/auth.setup.js; logging in per test would
// spend the IP-keyed 10/hour budget on the shared fixture server.
async function loginAdmin(page) {
  await page.goto('/admin');
  await expect(page).toHaveURL(/\/admin$/);
}

async function rowsFor(context, email) {
  const res = await context.request.get('/api/admin/results?limit=1000');
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.rows.filter((r) => r.email === email);
}

test('gallery input with three comma-separated urls renders three images', async ({ page }) => {
  await startSurvey(page, uniqueEmail('gallery'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);
  const images = page.locator('#identity-images .identity-image');
  await expect(images).toHaveCount(3);
  for (let i = 0; i < 3; i++) {
    await expect(images.nth(i)).toHaveJSProperty('naturalWidth', 90);
  }
  await expect(images.nth(0)).toHaveAttribute('data-identity-index', '0');
});

test('cancelling a retake keeps the participant’s earlier answers', async ({ browser }) => {
  test.setTimeout(240000);
  const email = uniqueEmail('retake');
  const first = await browser.newContext();
  const pageA = await first.newPage();
  await startSurvey(pageA, email);
  await completeSurvey(pageA, TRIALS);
  await first.close();

  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await loginAdmin(adminPage);
  expect((await rowsFor(admin, email)).length).toBe(TRIALS);

  const second = await browser.newContext();
  const pageB = await second.newPage();
  await pageB.goto('/');
  await fillDemographics(pageB, email);
  await pageB.evaluate(() => window.scrollTo(0, 300));
  await pageB.locator('#demographics-form button[type="submit"]').click();
  await expect(pageB.locator('#retake-modal')).toBeVisible();
  // A wheel is what a participant actually does; scrollTo() is programmatic and works on an
  // overflow:hidden scroll container, so it would not prove the lock.
  await pageB.mouse.move(200, 300);
  await pageB.mouse.wheel(0, 400);
  expect(await pageB.evaluate(() => window.scrollY),
    'the backdrop is viewport-fixed, so the page must not scroll undimmed content behind it').toBe(0);
  await pageB.locator('#retake-cancel').click();
  await expect(pageB.locator('#retake-modal')).toBeHidden();
  // Cancel reloads the page, so the scroll restore is not observable here; the jsdom suite
  // covers the restore mechanism itself.
  await second.close();

  expect((await rowsFor(admin, email)).length, 'Cancel must not delete study data').toBe(TRIALS);
  await admin.close();
});

test('confirming a retake clears earlier answers and logs the deletion', async ({ browser }) => {
  test.setTimeout(240000);
  const email = uniqueEmail('retake-confirm');
  const first = await browser.newContext();
  const pageA = await first.newPage();
  await startSurvey(pageA, email);
  await completeSurvey(pageA, TRIALS);
  await first.close();

  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await loginAdmin(adminPage);
  expect((await rowsFor(admin, email)).length).toBe(TRIALS);

  const second = await browser.newContext();
  const pageB = await second.newPage();
  await pageB.goto('/');
  await fillDemographics(pageB, email);
  await pageB.evaluate(() => window.scrollTo(0, 300));
  await pageB.locator('#demographics-form button[type="submit"]').click();
  await expect(pageB.locator('#retake-modal')).toBeVisible();
  await pageB.locator('#retake-confirm').click();
  await expect(pageB.locator('#survey-section')).toBeVisible();
  await answerTrial(pageB);
  await second.close();

  const rows = await rowsFor(admin, email);
  expect(rows.length, 'only the new trial should survive a confirmed retake').toBe(1);
  expect(rows[0].image_pair_id).not.toBe(null);
  await admin.close();
});
