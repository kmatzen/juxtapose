const { test, expect } = require('@playwright/test');
const {
  startSurvey, answerTrial, answerVisibleGroups, gotoTrialWithMask, currentTrialIsMaskFree,
  pairSignature, uniqueEmail,
} = require('./helpers/survey');

const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);

test('spatial mask pixels are decoded into per-identity binary masks', async ({ page }) => {
  await startSurvey(page, uniqueEmail('mask'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);
  await expect(page.locator('#mask-image')).toHaveJSProperty('complete', true);
  // The mask is (re)processed on first hover, which is also how a participant sees it.
  await page.locator('#identity-images .identity-image').first().hover();

  // script.js builds an entry for all ten IDENTITY_COLORS; only the fixture's three have pixels.
  await expect.poll(() => page.evaluate(
    () => Object.values(binaryMasks).filter((m) => m.matchCount > 100).length)).toBe(3);
  const masks = await page.evaluate(() => Object.entries(binaryMasks)
    .filter(([, m]) => m.matchCount > 100)
    .map(([i, m]) => ({ index: Number(i), width: m.width, matchCount: m.matchCount })));
  for (const m of masks) {
    expect(m.width).toBe(200);
    expect(m.matchCount, `identity ${m.index} must find its colour region`).toBeGreaterThan(100);
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
  await page.screenshot({ path: 'docs/screenshots/03-mask-overlay-hover.png', fullPage: true });
});

test('a single stacked gallery image slices into one square per panel', async ({ page }) => {
  await startSurvey(page, uniqueEmail('stacked'));
  expect(await gotoTrialWithMask(page, TRIALS)).toBe(true);

  const stacked = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 90;
    canvas.height = 270;
    const ctx = canvas.getContext('2d');
    ['#ff0000', '#00ff00', '#0000ff'].forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.fillRect(0, i * 90, 90, 90);
    });
    return canvas.toDataURL();
  });

  await page.evaluate((url) => {
    const container = document.getElementById('identity-images');
    container.innerHTML = '';
    loadStackedGallery(container, url, 'Stacked', []);
  }, stacked);

  const panels = page.locator('#identity-images .identity-image');
  await expect(panels).toHaveCount(3);
  await expect(panels.nth(1)).toHaveJSProperty('naturalWidth', 90);
  await expect(panels.nth(1)).toHaveJSProperty('naturalHeight', 90);

  const middleIsGreen = await panels.nth(1).evaluate((img) => {
    const c = document.createElement('canvas');
    c.width = c.height = 10;
    const ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0, 10, 10);
    const [r, g, b] = ctx.getImageData(5, 5, 1, 1).data;
    return { r, g, b };
  });
  expect(middleIsGreen).toEqual({ r: 0, g: 255, b: 0 });
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
