const { test, expect } = require('@playwright/test');
const { pageOverflow } = require('./helpers/admin');

test('the admin grid scrolls inside the page at phone width', async ({ page }) => {
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Toggle View' }).click();
  await expect(page.locator('#view-mode')).toHaveText('Responses View');

  const metrics = await pageOverflow(page);
  expect(metrics.overflow, 'no page-level horizontal scroll on a phone').toBeLessThanOrEqual(0);
  expect(metrics.gridScrollable, 'the grid must scroll inside its own container').toBe(true);
});
