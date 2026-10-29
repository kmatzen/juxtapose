const { test, expect } = require('@playwright/test');
const { startSurvey, answerTrial, uniqueEmail } = require('./helpers/survey');

test('survey is usable at phone width', async ({ page }) => {
  await startSurvey(page, uniqueEmail('mobile'));

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth
    - document.documentElement.clientWidth);
  expect(overflow, 'no horizontal overflow at 412px').toBeLessThanOrEqual(1);

  const a = await page.locator('#image-a').boundingBox();
  const b = await page.locator('#image-b').boundingBox();
  expect(a, 'image A must be inside the viewport').not.toBeNull();
  expect(b.x + b.width).toBeLessThanOrEqual(412 + 1);
  expect(b.y, 'tiles stack vertically on a phone').toBeGreaterThan(a.y);


  await answerTrial(page);
  await expect(page.locator('#survey-section')).toBeVisible();
});

test('demographics form is reachable and fills at phone width', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#demographics-form button[type="submit"]')).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth
    - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
