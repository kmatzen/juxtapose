const { test, expect } = require('@playwright/test');
const { startSurvey, answerTrial, uniqueEmail } = require('./helpers/survey');
const { startShotServer } = require('./helpers/screens');

const PORT = 5074;
const ROWS = 6;
const OWED = 3;
const SESSIONS = 5;

// Every other suite owes every pair, so app.py's random.sample branch — which pairs a session sees — never ran.
test('a session takes a sample of the study, and the sample varies', async ({ browser }) => {
  test.setTimeout(300000);
  const server = await startShotServer(PORT, { rows: String(ROWS), pairsPerUser: OWED, seed: null });
  const samples = new Set();

  try {
    for (let session = 0; session < SESSIONS; session += 1) {
      const context = await browser.newContext({ baseURL: server.base });
      const page = await context.newPage();
      await startSurvey(page, uniqueEmail('sample'));

      await expect(page.locator('#total-questions')).toHaveText(String(OWED));

      const promptOf = () => page.locator('#prompt-text').innerText();
      const rowOf = (text) => Number((text.match(/Trial (\d+)/) || [])[1]);

      const ids = [];
      let prompt = await promptOf();
      for (let trial = 0; trial < OWED; trial += 1) {
        expect(rowOf(prompt), `session ${session} trial ${trial}`).toBeGreaterThan(0);
        ids.push(rowOf(prompt));
        if (trial + 1 < OWED) {
          await answerTrial(page);
          await expect.poll(promptOf, { timeout: 15000 }).not.toBe(prompt);
          prompt = await promptOf();
        }
      }

      expect(ids).toHaveLength(OWED);
      expect(new Set(ids).size, 'a session should not be handed the same pair twice').toBe(OWED);
      samples.add([...ids].sort((a, b) => a - b).join(','));
      await context.close();
    }
  } finally {
    server.stop();
  }

  // 5 sessions drawing 3 of 6: 20 possible samples, so 5 identical draws costs 20^-4.
  expect(samples.size, 'which pairs a session is sampled from should vary').toBeGreaterThan(1);
});
