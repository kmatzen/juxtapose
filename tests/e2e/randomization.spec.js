const { test, expect } = require('@playwright/test');
const { startSurvey, answerTrial, uniqueEmail } = require('./helpers/survey');

// 8 sessions x 4 trials is 32 independent flips, so "all 32 landed the same way" costs 2^-31.
const SESSIONS = 8;
const TRIALS = parseInt(process.env.E2E_ROWS || '4', 10);

// The shot harness pins this randomisation for stable pixels; this suite proves it is still live.
test('pair order and A/B presentation vary across sessions', async ({ browser }, testInfo) => {
  test.setTimeout(300000);
  const orders = new Set();
  const orientations = new Set();

  for (let session = 0; session < SESSIONS; session += 1) {
    // A completed session is remembered by cookie: the same page cannot start a second study.
    const context = await browser.newContext({ baseURL: testInfo.project.use.baseURL });
    const page = await context.newPage();
    await startSurvey(page, uniqueEmail('rand'));
    const order = [];

    for (let trial = 0; trial < TRIALS; trial += 1) {
      const seen = await page.evaluate(() => ({
        prompt: document.getElementById('prompt-text')?.innerText || '',
        aTile: document.getElementById('image-a')?.src || '',
      }));
      // The fixture names rows by trial number: prompt "Trial 3" ships trial2_a.png / trial2_b.png.
      const row = (seen.prompt.match(/Trial (\d+)/) || [])[1];
      expect(row, `session ${session} trial ${trial} shows a known prompt`).toBeTruthy();

      order.push(row);
      const aFirst = seen.aTile.includes(`trial${Number(row) - 1}_a.png`);
      orientations.add(aFirst ? 'a-first' : 'b-first');

      if (trial + 1 < TRIALS) await answerTrial(page);
    }

    orders.add(order.join(','));
    expect(order).toHaveLength(TRIALS);
    await context.close();
  }

  expect(orders.size, 'the pairs a session sees should not come in the same order every time')
    .toBeGreaterThan(1);
  expect([...orientations].sort(), 'A and B should not keep the same assignment every time')
    .toEqual(['a-first', 'b-first']);
});
