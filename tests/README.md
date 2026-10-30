# Test Suite

This directory contains automated tests for the survey application, covering both backend (Python/Flask) and frontend (JavaScript) functionality.

## Test Summary

**Total: 329 tests passing -**
- Backend (Python): 113 tests
- Frontend (Vitest, jsdom): 192 tests
- Browser (Playwright/Chromium): 24 tests

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
pytest tests/test_data_logic.py::test_get_completed_pair_ids_with_prompt_question_disabled
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

```
tests/
├── __init__.py
├── conftest.py                     # Pytest fixtures and configuration
├── test_*.py                       # 113 backend tests, one file per area
├── frontend/
│   ├── setup.js                    # window flags, IntersectionObserver, console silencing
│   ├── helpers/survey-env.js       # DOM fixture mirroring index.html + fetch/Image stubs
│   ├── gallery.test.js             # 2  – image_gallery comma list vs stacked sheet
│   ├── hidden-section-validation.test.js  # 4  – hidden optional sections
│   ├── image-loading.test.js       # 11 – loadImagePair, in-flight lock, failure paths
│   ├── page-boot.test.js           # 6  – demographics gate, image lightbox
│   ├── progressive-questions.test.js      # 14 – navigation, completion, auto-advance, scroll
│   ├── submissions.test.js         # 16 – what the browser posts, retake confirmation
│   ├── tutorial.test.js            # 4  – tutorial walkthrough and submit gate
│   └── validation.test.js          # 10 – submit gating, CSRF lookup
├── e2e/
│   ├── README.md                   # fixture, coverage, the two regressions it killed
│   ├── fixture/{make_run.py,serve.py,server.sh}
│   ├── helpers/survey.js           # journey helpers against the live app
│   ├── survey-flow.spec.js         # 2  – whole study, resume after a reload
│   ├── canvas-overlay.spec.js      # 5  – mask decoding, hover overlay, slicing, optional columns
│   ├── retake-admin.spec.js        # 3  – gallery, retake cancel/confirm
│   ├── admin-dashboard.spec.js     # 3  – escaping, stats/paging, CSV shape
│   └── mobile-survey.spec.js       # 2  – phone-width layout
└── README.md                       # This file
```

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

## Key Test Cases

### 1. Survey Completion Bug Fix
**File**: `test_data_logic.py::test_completed_pairs_are_counted_once_per_trial`

**Why Important**: Fixed a bug where responses weren't counted as complete if prompt fields were NULL. Added `DISTINCT` to prevent duplicate counting.

### 2. Reset Session Functionality
**File**: `test_routes.py::test_reset_session_clears_data`

**Tests**: That "Start Over" properly clears session data

**Why Important**: Ensures users can restart the survey cleanly in dev mode.

### 3. Tutorial Flow
**File**: `frontend/tutorial.test.js`

**Tests**: Interactive tutorial walkthrough and form control

**Why Important**: Ensures new users understand the survey interface.

### 4. The Submit gate
**File**: `frontend/test/components/question-flow.test.ts`

**Tests**: Which radio groups gate Submit, including sections a pair cannot answer.

**Why Important**: Prevents incomplete submissions, and stops a hidden question from locking a
participant out of a study they have answered.

## Coverage Goals

Target: **80%+ coverage** for critical paths

Current coverage:
- - Backend: 78% (860 statements, 192 missed)
- - Frontend: components, services and model rules, run by `npm run test:unit`
- - Not covered by jsdom: canvas pixel readback and image decode, which the Playwright tier covers

## Adding New Tests

### Backend Tests (Python)

1. Create new test file: `tests/test_yourfeature.py`
2. Import fixtures from `conftest.py`
3. Follow naming convention: `test_*` functions
4. Use `client` fixture for route tests
5. Use `app` fixture for application context

Example:
```python
def test_my_feature(client, sample_demographics):
    # Arrange
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-123'
    
    # Act
    response = client.get('/my-route')
    
    # Assert
    assert response.status_code == 200
```

### Frontend Tests (TypeScript)

1. Create `frontend/test/components/yourfeature.test.ts` — every component suite carries the
   `@vitest-environment jsdom` pragma.
2. `surveyFixture()` for the page, `fakeApi(routes)` for the network, `answer()` for radios.
3. Mount the real component, drive it through its props, assert on the DOM it left behind, dispose it.

```typescript
// @vitest-environment jsdom
import { mountTrialRunner } from '../../src/components/trial-runner';
import { fakeApi } from '../helpers/api';
import { surveyFixture } from '../helpers/dom';

test('a pair that is not owed ends the session', async () => {
    surveyFixture();
    const runner = mountTrialRunner(document.body, {
        api: createSurveyApi(fakeApi({ '/api/get_image_pair': { ok: false, status: 404 } }).fetch),
        // ...the components the runner drives, as props
    });

    await runner.loadPair(0);

    expect(navigate).toHaveBeenCalledWith('/');
});
```

## Test Configuration

### Backend (pytest)
- Configuration file: `pytest.ini`
- Test discovery: `tests/` directory
- Coverage target: `src/survey/`
- Test database: Temporary SQLite

### Frontend (Vitest)
- Configuration: `frontend/vitest.config.mts`
- Test environment: `jsdom`
- Test discovery: `frontend/test/**/*.test.ts`
- Runs against TypeScript sources directly; no build step

## CI/CD Integration

These tests can be run automatically on:
- Git pre-commit hooks
- GitHub Actions workflows
- Before deployment
- Pull request validation

Example GitHub Actions:
```yaml
- name: Run backend tests
  run: uv run pytest -v
  
- name: Run frontend tests
  run: npm run test:unit
```

## Troubleshooting

**Import errors (Python)**: Make sure you're running from project root

**Database errors (Python)**: Tests use temporary SQLite databases that are cleaned up automatically

**Fixture not found (Python)**: Check `conftest.py` for available fixtures

**Module not found (JavaScript)**: Run `npm install` to install dependencies

**Tests fail with CORS errors (JavaScript)**: These are mocked in jsdom environment

**Registry errors (npm)**: Configure npm to use public registry:
```bash
npm config set registry https://registry.npmjs.org/
```

## Coverage Reports

### Backend Coverage
```bash
pytest --cov=src/survey --cov-report=html
open htmlcov/index.html
```

### Frontend Coverage
```bash
npm run test:coverage
open coverage-frontend/index.html
```

## Continuous Improvement

Future test additions:
- [ ] API integration tests
- [ ] Database migration tests
- [ ] Performance/load tests
- [ ] Accessibility tests
- [ ] Cross-browser compatibility tests
