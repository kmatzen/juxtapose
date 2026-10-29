const { test, expect } = require('@playwright/test');
const { startSurvey, uniqueEmail } = require('./helpers/survey');

const PASSWORD = process.env.ADMIN_PASSWORD || 'e2e-admin-password';
const PAYLOAD = '<img src=x onerror="window.__xss=1">';

async function loginAdmin(page) {
  await page.goto('/admin/login');
  await page.fill('#password', PASSWORD);
  await page.locator('form').evaluate((f) => f.submit());
  await expect(page).toHaveURL(/\/admin$/);
}

test('participant-submitted answers reach the dashboard as text, not markup', async ({ browser }) => {
  const email = uniqueEmail('xss');
  const participant = await browser.newContext();
  const page = await participant.newPage();
  let dialogs = 0;
  page.on('dialog', async (d) => { dialogs++; await d.dismiss(); });
  await startSurvey(page, email);

  const status = await page.evaluate(async ([payload]) => {
    const token = document.querySelector('meta[name="csrf-token"]').content;
    const pair = await (await fetch('/api/get_image_pair/0')).json();
    const res = await fetch('/api/submit_survey', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
      body: JSON.stringify({
        image_pair_id: pair.id,
        stimulus_data: pair,
        responses: { image_quality: { choice: payload, confidence: 3 } },
        was_randomized: pair.was_randomized,
        time_spent: 5,
      }),
    });
    return res.status;
  }, [PAYLOAD]);
  expect(status).toBe(200);
  await participant.close();

  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  adminPage.on('dialog', async (d) => { dialogs++; await d.dismiss(); });
  await loginAdmin(adminPage);
  await adminPage.locator('#results-body tr').first().waitFor();
  await adminPage.locator('button:has-text("Toggle View")').click();
  await expect(adminPage.locator('#view-mode')).toHaveText('Responses View');

  await expect(adminPage.locator('#results-body img')).toHaveCount(0);
  await expect(adminPage.locator('#results-body')).toContainText(PAYLOAD);
  expect(await adminPage.evaluate(() => window.__xss)).toBeUndefined();
  expect(dialogs).toBe(0);
  await adminPage.screenshot({ path: 'docs/screenshots/05-admin-dashboard.png', fullPage: true });
  await admin.close();
});

test('stats and paging serve the dashboard without shipping the study', async ({ browser }) => {
  const admin = await browser.newContext();
  const page = await admin.newPage();
  await loginAdmin(page);

  const stats = await (await admin.request.get('/api/admin/stats')).json();
  expect(stats.responses).toBeGreaterThan(0);
  expect(stats.participants).toBeGreaterThan(0);

  const first = await (await admin.request.get('/api/admin/results?limit=1&offset=0')).json();
  expect(first.rows).toHaveLength(1);
  expect(first.limit).toBe(1);
  expect(first.total).toBe(stats.responses);

  const last = await (await admin.request.get(`/api/admin/results?limit=1&offset=${first.total - 1}`)).json();
  expect(last.rows).toHaveLength(1);
  const beyond = await (await admin.request.get(`/api/admin/results?limit=1&offset=${first.total}`)).json();
  expect(beyond.rows).toHaveLength(0);
  await admin.close();
});

test('csv export carries exactly one column per value', async ({ browser }) => {
  const admin = await browser.newContext();
  const page = await admin.newPage();
  await loginAdmin(page);

  const csv = await (await admin.request.get('/api/admin/export')).text();
  const header = csv.split('\n')[0].split(',');
  const dupes = header.filter((h, i) => header.indexOf(h) !== i);
  expect(dupes, `duplicate CSV columns: ${dupes.join(', ')}`).toEqual([]);
  expect(header.filter((h) => h.endsWith('_choice')).length).toBeGreaterThan(0);
  expect(header.filter((h) => h.endsWith('_confidence')).length).toBeGreaterThan(0);
  expect(header.filter((h) => h === 'better_image').length).toBe(0);
  await admin.close();
});
