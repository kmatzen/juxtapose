const { test, expect, devices } = require('@playwright/test');
const { fillDemographics } = require('./helpers/survey');
const { startShotServer, pinRandom, shot } = require('./helpers/screens');

const PORT = 5072;
const EMAIL = 'shot-mobile@example.com';

test('the committed phone screenshots come from the same deterministic study', async ({ browser }) => {
  test.setTimeout(240000);
  const server = await startShotServer(PORT);
  const context = await browser.newContext({ ...devices['Pixel 7'], baseURL: server.base });
  await pinRandom(context);
  const page = await context.newPage();

  try {
    await page.goto('/');
    await expect(page.locator('#demographics-section')).toBeVisible();
    await fillDemographics(page, EMAIL);
    await shot(page, '07-mobile-demographics');

    await page.locator('#demographics-form button[type="submit"]').click();
    await expect(page.locator('#survey-section')).toBeVisible();
    await expect(page.locator('#image-a')).toHaveJSProperty('naturalWidth', 200);
    await shot(page, '06-mobile-survey');
  } finally {
    await context.close();
    server.stop();
  }
});
