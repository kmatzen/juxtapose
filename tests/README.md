# Test Suite

This directory contains automated tests for the survey application, covering both backend (Python/Flask) and frontend (JavaScript) functionality.

## Test Summary

Three tiers, counted by running them, not by a number pasted into this file:

```bash
uv run pytest tests -q                      # backend
npm run test:unit                           # frontend model, services and components
npm run test:e2e                            # real browser, boots its own app
```

Frontend suites import the shipped `frontend/src` modules directly — the component under test is
the component the page runs. Never re-implement app logic inside a test: an inline copy passes
while the shipped code rots.

The Playwright tier drives the running app in Chromium and owns what jsdom cannot do:
canvas mask decoding, image decoding, phone-width layout, whole-study journeys
(`tests/e2e/README.md`).

## Setup

### Backend Tests
Install Python test dependencies:

```bash
uv pip install .[dev]
```

or

```bash
pip install ".[dev]"
```

### Frontend Tests
Install JavaScript test dependencies:

```bash
npm install
npm exec playwright install chromium   # browser tier only
```

## Running Tests

### Run All Tests (Backend + Frontend):
```bash
# Backend tests
uv run pytest -v

# Frontend unit tests (Vitest, imports frontend/src modules directly)
npm run test:unit

# Browser tests (boots its own app + fixture study)
npm run test:e2e

# Everything
uv run pytest -v && npm run test:unit && npm run test:e2e
```

### Backend Tests (Python)

**Run all tests:**
```bash
pytest
```

**Run with coverage report:**
```bash
pytest --cov=src/survey --cov-report=html
```

Then open `htmlcov/index.html` in your browser to see detailed coverage.

**Run specific test file:**
```bash
pytest tests/test_routes.py
```

**Run specific test:**
```bash
pytest tests/test_data_logic.py::test_get_completed_pair_ids_incomplete_responses
```

**Run with verbose output:**
```bash
pytest -v
```

**Run and stop at first failure:**
```bash
pytest -x
```

### Frontend Tests (JavaScript)

One runner for everything under `frontend/src`, in a DOM:

| Tier | Runner | Files | Needs a build? |
|------|--------|-------|----------------|
| Model, services, components | Vitest | `frontend/test/**/*.test.ts` | no, imports `.ts` directly |
| Real browser behaviour | Playwright | `tests/e2e/*.spec.js` | yes, `pretest:e2e` builds it |

**Run the unit tests:**
```bash
npm run test:unit
```

**Run one file, or watch a pattern:**
```bash
npx vitest run --config frontend/vitest.config.mts test/components/trial-runner.test.ts
npx vitest --config frontend/vitest.config.mts test/components
```

jsdom has no canvas and no image decode, so anything that reads pixels or waits on a tile belongs
in the Playwright tier, not a jsdom mock of it.

## Test Structure

One file per area, and the area is named in the file name.

```
tests/
├── conftest.py                       # _boot_app: boots the app on a study the test wrote, CSRF helpers
├── fixtures/export_snapshot.csv      # the export's column contract, golden
├── e2e/                              # real-browser tier; its fixture and notes: e2e/README.md
├── boot, env and gates
│   test_app_env.py test_scale_gate.py test_config_setup.py test_config_not_on_request_path.py
│   test_no_debugger.py test_dev_database_path.py test_proxy_ip.py test_assets.py test_security.py
├── routes, sessions and the referral gate
│   test_routes.py test_api_endpoints.py test_results_path.py test_csrf_forms.py
│   test_referral_gate.py test_referral_trace.py test_rate_limit.py
├── what a session is shown, and what counts as answered
│   test_trial_store.py test_trial_input_lookup.py test_pair_flip.py test_stimulus_integrity.py
│   test_progress_by_participant.py test_resume.py test_resume_budget.py test_visibility_rule.py
│   test_data_logic.py
├── answers: shape, ranges and timing
│   test_submit_integrity.py test_answer_shapes.py test_stats_answer_shape.py test_required_free_text.py
│   test_question_options_gate.py test_timing_flag.py test_time_spent.py
├── participants, retakes and privacy
│   test_retake.py test_retake_ownership.py test_demographics_uniqueness.py test_audit_log_pii.py
├── admin: what the study owner sees
│   test_admin.py test_admin_participants.py test_admin_statistics.py test_admin_pagination.py
│   test_admin_password_compare.py test_admin_query_agreement.py test_export_stream.py
│   test_export_answer_types.py test_flatten_result.py
├── the database under load
│   test_concurrent_submit.py test_db_indexes.py test_audit_five_cleanups.py
└── the tooling the tests depend on
    test_e2e_fixture_writer.py test_docs_contract.py
```

`test_docs_contract.py` is in the tree because it is a test with teeth: it fails when a doc names a
file that is not there, an env var the app reads is missing from the README, or the security mode is
documented from two places.

## What's Tested

### Backend Routes (`test_routes.py`)
- - Index page loads correctly
- - API config endpoint returns data
- - Demographics submission validation
- - Session management and reset
- - Tutorial route access control
- - Admin authentication

### Backend Data Logic (`test_data_logic.py`)
- - Completed pair detection (critical bug fix)
- - Multiple participants with same email
- - Empty result handling

### Frontend components (`frontend/test/`)
Each suite mounts the real component into the page fixture (`test/helpers/dom.ts`) and drives it
through its props, with `fakeApi` for the network and injected seams for canvas and image decode.

- - `trial-runner` — which page the participant lands on, pair loading, counters, the payload for
  `ab_preference` / `likert` / `free_text` / `multiple_choice`, per-pair timing, every failure path,
  the walkthrough's submit path, dev auto-fill
- - `stimulus-view` — preload, the lock while images are in flight, CORS, commit, lightbox binding
- - `conditioning-tiles` — comma-list and stacked galleries, mask tiles, hover/tap overlays, cleanup
- - `question-flow` — visibility per pair, submit gating, navigation, auto-advance, layout
- - `retake-modal`, `tutorial-banner`, `demographics-form`, `lightbox`, `error-banner`, `device-panel`
- - `study-state` — the rules with no DOM: responses, submission, progress, masks, tutorial steps

## Reading order for the rules that have already burned someone

- **Progress is a session's own rows** - `test_progress_by_participant.py`; the resume promise that
  a person's cap spans their address is `test_resume_budget.py`.
- **A `depends_on` question is exempt only where its input is blank** - `test_visibility_rule.py`.
- **An off-scale answer must never reach an average** - `test_answer_shapes.py`; the aggregate still
  has to survive rows stored before that boundary, `test_stats_answer_shape.py`.
- **A retake delete needs the session to own the email** - `test_retake_ownership.py`.
- **One query serves the admin list and the CSV export** - `test_admin_query_agreement.py`.
- **The docs match the tree** - `test_docs_contract.py`.
