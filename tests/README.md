# Test Suite

This directory contains automated tests for the survey application, covering both backend (Python/Flask) and frontend (JavaScript) functionality.

## Test Summary

**Total: 180 tests passing -**
- Backend (Python): 104 tests
- Frontend (JavaScript): 76 tests

Frontend suites `require()` the real `src/survey/static/script.js` (the file ends
with a browser-inert `module.exports` guard). Never re-implement app logic inside a
test: an inline copy passes while the shipped script rots.

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
```

## Running Tests

### Run All Tests (Backend + Frontend):
```bash
# Backend tests
uv run pytest -v

# Frontend tests
npm test

# Both together
uv run pytest -v && npm test
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

**Run all tests:**
```bash
npm test
```

**Run tests in watch mode:**
```bash
npm run test:watch
```

**Run with coverage:**
```bash
npm run test:coverage
```

Then open `coverage/lcov-report/index.html` for detailed frontend coverage.

**Run specific test file:**
```bash
npm test -- frontend/validation.test.js
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                     # Pytest fixtures and configuration
├── test_*.py                       # 104 backend tests, one file per area
├── frontend/
│   ├── setup.js                    # window flags, IntersectionObserver, console silencing
│   ├── helpers/survey-env.js       # DOM fixture mirroring index.html + fetch/Image stubs
│   ├── admin-render.test.js        # 9  – admin table escaping and rendering
│   ├── gallery.test.js             # 2  – image_gallery comma list vs stacked sheet
│   ├── hidden-section-validation.test.js  # 4  – hidden optional sections
│   ├── image-loading.test.js       # 11 – loadImagePair, in-flight lock, failure paths
│   ├── page-boot.test.js           # 6  – demographics gate, image lightbox
│   ├── progressive-questions.test.js      # 14 – navigation, completion, auto-advance, scroll
│   ├── submissions.test.js         # 16 – what the browser posts, retake confirmation
│   ├── tutorial.test.js            # 4  – tutorial walkthrough and submit gate
│   └── validation.test.js          # 10 – submit gating, CSRF lookup
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
- - `ENABLE_PROMPT_QUESTION` flag handling
- - Multiple participants with same email
- - Empty result handling

### Frontend (`frontend/*.test.js`)
Every suite loads the real `script.js` through `helpers/survey-env.js`, which builds
the page the way `index.html` does and stubs fetch, `Image`, scrolling and
`IntersectionObserver`.

- - Which page the participant lands on, and the image lightbox
- - Pair loading: prompt, images, counters, the lock while images are in flight, every failure path
- - Question navigation, per-section completion, auto-advance, scroll tracking
- - Submit gating, including sections hidden by `depends_on`
- - The payload posted for `ab_preference`, `likert`, `free_text` and `multiple_choice`
- - The retake warning: the destructive delete only runs after confirmation
- - Tutorial walkthrough and the submit lock it holds
- - CSRF token lookup; admin table escaping

## Key Test Cases

### 1. Survey Completion Bug Fix
**File**: `test_data_logic.py::test_get_completed_pair_ids_with_prompt_question_disabled`

**Tests**: That survey completion works correctly when `ENABLE_PROMPT_QUESTION=false`

**Why Important**: Fixed a bug where responses weren't counted as complete if prompt fields were NULL. Added `DISTINCT` to prevent duplicate counting.

### 2. Reset Session Functionality
**File**: `test_routes.py::test_reset_session_clears_data`

**Tests**: That "Start Over" properly clears session data

**Why Important**: Ensures users can restart the survey cleanly in dev mode.

### 3. Tutorial Flow
**File**: `frontend/tutorial.test.js`

**Tests**: Interactive tutorial walkthrough and form control

**Why Important**: Ensures new users understand the survey interface.

### 4. Form Validation
**File**: `frontend/validation.test.js`

**Tests**: Complete form validation logic

**Why Important**: Prevents incomplete survey submissions.

## Coverage Goals

Target: **80%+ coverage** for critical paths

Current coverage:
- - Backend: 78% (860 statements, 192 missed)
- - Frontend: 70% of statements (`script.js` 69%, `admin.js` 83%); `npm run test:coverage` fails below the thresholds in `jest.config.js`
- - Not covered in the browser suites: canvas mask-overlay rendering and the dev-mode auto-fill helpers

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

### Frontend Tests (JavaScript)

1. Create a new file: `tests/frontend/yourfeature.test.js`
2. `require('./helpers/survey-env')` for the page fixture, API mock and answer helpers
3. Call the real `script.<function>()`; assert on the DOM it left behind

Example:
```javascript
const { loadSurvey, script, surveyDom } = require('./helpers/survey-env');

describe('My Feature', () => {
    beforeEach(async () => {
        surveyDom();
        await loadSurvey();
    });

    test('the app does the thing', () => {
        script.setupSubmitValidation();
        expect(document.getElementById('submit-btn').disabled).toBe(true);
    });
});
```

## Test Configuration

### Backend (pytest)
- Configuration file: `pytest.ini`
- Test discovery: `tests/` directory
- Coverage target: `src/survey/`
- Test database: Temporary SQLite

### Frontend (Jest)
- Configuration: `jest.config.js`
- Test environment: `jsdom` (browser simulation)
- Test discovery: `tests/frontend/**/*.test.js`
- Coverage target: `src/survey/static/**/*.js`

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
  run: npm test
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
- [ ] End-to-end tests using Playwright
- [ ] API integration tests
- [ ] Database migration tests
- [ ] Performance/load tests
- [ ] Accessibility tests
- [ ] Cross-browser compatibility tests
