const { expect } = require('@playwright/test');

const RUN_DIR = process.env.E2E_RUN_DIR || `${process.env.TMPDIR || '/tmp'}juxtapose-e2e`;

async function fillDemographics(page, email) {
  await page.fill('#email', email);
  for (const select of await page.locator('#demographics-form select').all()) {
    await select.selectOption({ index: 1 });
  }
  for (const group of await page.locator('#demographics-form .radio-group').all()) {
    await group.locator('input[type="radio"]').first().check();
  }
  for (const box of await page.locator('#demographics-form .checkbox-group input[type="checkbox"]').all()) {
    await box.check();
  }
  for (const num of await page.locator('#demographics-form input[type="number"]').all()) {
    await num.fill('3');
  }
  for (const txt of await page.locator('#demographics-form input[type="text"], #demographics-form textarea').all()) {
    await txt.fill('e2e');
  }
  const consent = page.locator('#demographics-form input[name="consent"]');
  if (await consent.count()) {
    await consent.check();
  }
}

async function submitDemographics(page, email) {
  await page.goto('/');
  await expect(page.locator('#demographics-section')).toBeVisible();
  await fillDemographics(page, email);
  await page.locator('#demographics-form button[type="submit"]').click();
}

async function startSurvey(page, email) {
  await submitDemographics(page, email);
  await expect(page.locator('#survey-section')).toBeVisible();
  await expect(page.locator('#image-a')).toHaveJSProperty('naturalWidth', 200);
}

// The styled radios sit under labels, so click the label: check() on the input waits for
// visibility of an element the CSS hides, which costs the full action timeout per question.
async function answerVisibleGroups(page) {
  const groups = page.locator('#survey-form .evaluation-section:visible .radio-group, #survey-form .evaluation-section:visible .likert-scale');
  for (let guard = 0; guard < 16; guard++) {
    const count = await groups.count();
    let answered = false;
    for (let i = 0; i < count; i++) {
      const group = groups.nth(i);
      if (!(await group.isVisible().catch(() => false))) {
        continue;
      }
      if (await group.locator('input:checked').count()) {
        continue;
      }
      const label = group.locator('label').first();
      if (!(await label.count())) {
        continue;
      }
      await label.click({ timeout: 3000 }).catch(() => {});
      answered = true;
      break;
    }
    if (!answered) {
      return;
    }
  }
}

// Radios auto-advance, so answer the visible group and only click Next when the index did not move.
async function answerTrial(page) {
  const total = parseInt(await page.locator('#total-questions').innerText(), 10) || 10;
  const submit = page.locator('#submit-btn');
  for (let step = 0; step < total * 3; step++) {
    await answerVisibleGroups(page);
    if (await submit.isEnabled()) {
      // The button flips to disabled when an auto-advance moves on, so a losing click is a
      // state change to re-read, not a failure.
      if (await submit.click({ timeout: 4000 }).then(() => true).catch(() => false)) {
        return;
      }
      continue;
    }
    const before = await page.locator('#current-question').innerText();
    await page.locator('#next-question-btn').click({ timeout: 4000 }).catch(() => {});
    await expect(page.locator('#current-question')).not.toHaveText(before, { timeout: 5000 }).catch(() => {});
  }
  throw new Error('trial never reached an enabled submit button');
}

function pairSignature(page) {
  return page.evaluate(() => (document.getElementById('image-a')?.src || '').slice(-64)
    + '|' + (document.getElementById('prompt-text')?.innerText || ''));
}

async function completeSurvey(page, trials) {
  for (let i = 0; i < trials; i++) {
    const before = i + 1 < trials ? await pairSignature(page) : null;
    await answerTrial(page);
    if (i + 1 < trials) {
      await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
    }
  }
  await expect(page.getByRole('heading', { name: 'Thank You!' })).toBeVisible({ timeout: 20000 });
}

// The tiles are not cleared between trials, so the served pair's data is the truth here.
function currentTrialIsMaskFree(page) {
  return page.evaluate(() => !currentImageData?.mask_url && !currentImageData?.identity_urls);
}

// Trial order is a per-session shuffle, so walk the study until a trial with a mask shows up.
async function gotoTrialWithMask(page, trials) {
  for (let i = 0; i < trials; i++) {
    if (!(await currentTrialIsMaskFree(page))) {
      return true;
    }
    if (i === trials - 1) {
      return false;
    }
    const before = await pairSignature(page);
    await answerTrial(page);
    await expect.poll(() => pairSignature(page), { timeout: 15000 }).not.toBe(before);
  }
  return false;
}

const uniqueEmail = (tag) => `e2e-${tag}-${Date.now()}@example.com`;

module.exports = {
  RUN_DIR, answerVisibleGroups, fillDemographics, submitDemographics, startSurvey, answerTrial,
  completeSurvey, gotoTrialWithMask, currentTrialIsMaskFree, pairSignature, uniqueEmail,
};
