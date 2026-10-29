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
same-origin. Images cannot be `data:` URIs: `script.js` sets `crossOrigin='anonymous'` for
canvas access and Chromium refuses `data:` URIs under CORS, so every tile fails to load.

Override with `E2E_ROWS`, `E2E_RUN_DIR`, `PYTHON` (default `/tmp/jlvenv/bin/python`),
`E2E_PORT`. Trial order is a per-session shuffle, so specs read the served pair's data
(`currentImageData`) rather than assuming an index.

## Coverage

| Spec | Proves |
|---|---|
| `survey-flow.spec.js` | demographics → 4 trials → thank-you; reload mid-study |
| `canvas-overlay.spec.js` | mask pixels decoded into per-identity masks; hover paints the overlay on both outputs; stacked gallery slicing; empty optional column is submittable |
| `retake-admin.spec.js` | comma-separated gallery = N images; Cancel keeps answers; confirm deletes them |
| `admin-dashboard.spec.js` | participant-supplied text renders as text; stats + paging; CSV one column per value |
| `mobile-survey.spec.js` | no horizontal overflow at phone width, tiles stack |

`docs/screenshots/` is written by the suite and committed so the PR can show the app.

## Two tests are `fixme` — they document live defects

- `reloading mid-study resumes on an unserved trial`: `get_image_pair` maps index 0 to the
  first *assigned* trial, not the first *uncompleted* one, so reloading after 2 of 4 trials
  re-serves trial 1.
- `a trial with empty optional columns hides the mask and identity tiles`:
  `displayConditioningInputs` sets `identitySection.style.display='block'` unconditionally
  and only touches `#mask-image` / the gallery container when the value is non-empty, so a
  trial with an empty `mask_url` shows the **previous** trial's mask and identity images
  while the questions for them are correctly hidden. `survey_config.yaml` documents
  `optional` as "Hide when column value is empty".
