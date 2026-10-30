# Browser (Playwright) tests

Real Chromium, real Flask app, real canvas. These exist for the surfaces jsdom cannot
reach: 2D canvas mask decoding, image decoding, layout at phone width, and full
participant journeys through the running study.

```bash
npm ci
npm run test:e2e            # headless, boots its own server on :5055
npm run test:e2e:headed     # watch it run
npm run test:e2e:report     # open the HTML report (traces on failure)
```

## Fixture

`fixture/server.sh` builds a throwaway study in `$TMPDIR/juxtapose-e2e` and boots the app
against it: `make_run.py` writes a config (4 trials, tutorial off), `trials.tsv`, and PNG
images; `serve.py` runs the real app plus one route (`/e2e-img/...`) so images are
same-origin. Images cannot be `data:` URIs: the stimulus tiles set `crossOrigin='anonymous'` for
canvas access and Chromium refuses `data:` URIs under CORS, so every tile fails to load.

Override with `E2E_ROWS`, `E2E_RUN_DIR`, `PYTHON` (default `/tmp/jlvenv/bin/python`),
`E2E_PORT`. Trial order is a per-session shuffle, so specs read the served pair's data
(`.mask-tile`, `#identity-section`) rather than assuming an index.

## Coverage

| Spec | Proves |
|---|---|
| `survey-flow.spec.js` | demographics → 4 trials → thank-you; reload mid-study |
| `canvas-overlay.spec.js` | mask pixels decoded into per-identity masks; hover paints the overlay on both outputs; stacked gallery slicing; empty optional column is submittable |
| `retake-admin.spec.js` | comma-separated gallery = N images; Cancel keeps answers; confirm deletes them |
| `admin-dashboard.spec.js` | participant-supplied text renders as text; stats + paging; CSV one column per value; grid stays inside the page |
| `mobile-admin.spec.js` | the wide admin grid scrolls inside its container at phone width |
| `mobile-survey.spec.js` | no horizontal overflow at phone width, tiles stack |

`docs/screenshots/` is written by the suite and committed so the PR can show the app.

## Two regressions this suite found and killed

- **Resume re-served answered trials.** `get_image_pair` served `user_image_pairs[index]`, and
  a reload restores the pre-completion assignment, so a participant who reloaded after 2 of 4
  trials got trial 1 back. Completed trials are now skipped in place — the client counts indices
  against the assignment, so filtering the list would shift it and skip trials — and the pair
  payload carries `trials_remaining` so the counter shows the true position after a reload.
- **Empty optional columns showed the previous trial's images.** `displayConditioningInputs`
  forced `#identity-section` visible and only touched `#mask-image` and the identity container
  when the incoming value was non-empty, so a trial with an empty `mask_url` kept the previous
  trial's mask on screen while its mask questions were correctly hidden: a rating recorded
  against a mask the trial does not have. `clearConditioningTiles()` now runs first, and both
  tiles hide when their column is empty.

The fixture ships two optional-free rows because the app samples trials per session: one row
could be sampled out and the case would silently stop being covered.

## Two things that bite

- The webServer runs `npm run build` first. Plain `npx playwright test` skips the `pretest:e2e`
  hook, and a stale `src/survey/static_dist/` then serves a page your test never wrote.
- `/admin/login` is rate-limited per IP (10/hour) and every test shares one 127.0.0.1.
  `auth.setup.js` signs in once and hands the session to the other projects via storageState,
  so specs `goto('/admin')` instead of logging in.
