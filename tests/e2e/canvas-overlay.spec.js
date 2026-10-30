const { test, expect } = require('@playwright/test');
const {
  startSurvey, answerTrial, answerVisibleGroups, gotoTrialWithMask, currentTrialIsMaskFree,
  pairSignature, uniqueEmail,
} = require('./helpers/survey');

const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);
// The same table the app scans and the fixture paints with — the overlay must come back in it.
const PALETTE = require('../../frontend/src/identity-colors.json');
const EXPECTED_COLOURS = PALETTE.slice(0, 3).map(([r, g, b]) => `${r},${g},${b}`);
const paletteColour = (index) => {
  const [r, g, b] = PALETTE[index];
  return { r, g, b };
};

// The mask decoder is a pure model function with unit tests; what only a browser can prove is that
// every identity colour in the fixture's sheet arrives as that identity's own painted region.
test('each identity paints its own colour region on the outputs', async ({ page }) => {
  await startSurvey(page, uniqueEmail('masks'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);

  const tiles = page.locator('#identity-images .identity-image');
  await expect(tiles).toHaveCount(3);

  for (let index = 0; index < 3; index += 1) {
    await tiles.nth(index).hover();
    const painted = await page.locator('canvas.mask-overlay').first().evaluate((canvas) => {
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      const counts = {};
      let opaque = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i + 3] > 0) {
          opaque += 1;
          const key = `${data[i]},${data[i + 1]},${data[i + 2]}`;
          counts[key] = (counts[key] || 0) + 1;
        }
      }
      const [colour, region] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] || [];
      return { opaque, region, colour };
    });

    // The fixture's mask sheet is one 60x60 block per identity in identity colour.
    expect(painted.colour, `identity ${index} paints in its own colour`).toBe(EXPECTED_COLOURS[index]);
    expect(painted.region, `identity ${index} must find its region`).toBeGreaterThan(3000);
    expect(painted.opaque).toBeLessThan(200 * 150 / 2);
    await page.mouse.move(0, 0);
  }
});

test('hovering an identity image paints a mask overlay over both outputs', async ({ page }) => {
  await startSurvey(page, uniqueEmail('overlay'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);

  await page.locator('#identity-images .identity-image').first().hover();
  const overlays = page.locator('canvas.mask-overlay');
  await expect(overlays).toHaveCount(2);

  const painted = await overlays.first().evaluate((canvas) => {
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let opaque = 0;
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] > 0) opaque++;
    }
    return { opaque, total: canvas.width * canvas.height };
  });

  expect(painted.total).toBe(200 * 150);
  expect(painted.opaque, 'the identity region is 60x60 of the mask').toBeGreaterThan(3000);
  expect(painted.opaque, 'overlay must stay local to the identity region').toBeLessThan(painted.total / 2);
});

// The slicing math is unit-tested; the browser proves the real sheet on the real page arrives as
// N square tiles, in order, with the middle panel's pixels.
test('the stacked identity sheet arrives as one square tile per panel', async ({ page }) => {
  await startSurvey(page, uniqueEmail('stacked'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);

  const panels = page.locator('#identity-images .identity-image');
  const count = await panels.count();
  expect(count).toBeGreaterThan(1);
  await expect(panels.first()).toHaveJSProperty('complete', true);

  const geometry = await panels.evaluateAll((images) => images.map((img, index) => ({
    index: Number(img.getAttribute('data-identity-index')),
    square: img.naturalWidth > 0 && img.naturalWidth === img.naturalHeight,
  })));
  expect(geometry.map((g) => g.index)).toEqual([...Array(count).keys()]);
  expect(geometry.every((g) => g.square)).toBe(true);

  const middle = await panels.nth(1).evaluate((img) => {
    const c = document.createElement('canvas');
    c.width = c.height = 10;
    const ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0, 10, 10);
    const [r, g, b] = ctx.getImageData(5, 5, 1, 1).data;
    return { r, g, b };
  });
  expect(middle).toEqual(paletteColour(1));
});

test('the trial with no mask is submittable and the study completes', async ({ page }) => {
  test.setTimeout(180000);
  await startSurvey(page, uniqueEmail('optional'));

  let sawMaskFreeTrial = false;
  for (let i = 0; i < TRIALS; i++) {
    if (await currentTrialIsMaskFree(page)) {
      sawMaskFreeTrial = true;
      // Audit #5: answering only the visible questions must be enough to submit.
      await answerVisibleGroups(page);
      await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 20000 });
    }
    const before = await pairSignature(page);
    await answerTrial(page);
    if (i < TRIALS - 1) {
      await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
    }
  }

  expect(sawMaskFreeTrial, 'fixture must serve a trial with an empty optional column').toBe(true);
  await expect(page.getByRole('heading', { name: 'Thank You!' })).toBeVisible({ timeout: 20000 });
});

test('a trial with empty optional columns hides the mask and identity tiles', async ({ page }) => {
  await startSurvey(page, uniqueEmail('stale'));

  let found = false;
  for (let i = 0; i < TRIALS - 1 && !found; i++) {
    const hadMask = !(await currentTrialIsMaskFree(page));
    const before = await pairSignature(page);
    await answerTrial(page);
    await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
    found = hadMask && (await currentTrialIsMaskFree(page));
  }
  test.skip(!found, 'the mask-free trial came last in this session shuffle');

  await expect(page.locator('#identity-section'),
    'survey_config.yaml:156 promises optional inputs hide when the column is empty').toBeHidden();
  await expect(page.locator('#mask-image')).toBeHidden();
});
