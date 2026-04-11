# Test Suite

This directory contains automated tests for the survey application, covering both backend (Python/Flask) and frontend (JavaScript) functionality.

## Test Summary

**Total: 45 tests passing -**
- Backend (Python): 11 tests
- Frontend (JavaScript): 34 tests

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
├── conftest.py                 # Pytest fixtures and configuration
├── test_routes.py              # Backend route tests (7 tests)
├── test_data_logic.py          # Backend data logic tests (4 tests)
├── frontend/
│   ├── setup.js                # Frontend test setup
│   ├── validation.test.js      # Form validation tests (17 tests)
│   └── tutorial.test.js        # Tutorial functionality tests (17 tests)
└── README.md                   # This file
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

### Frontend Validation (`frontend/validation.test.js`)
- - Form validation logic
- - Submit button state management
- - Radio button interactions
- - Incomplete form detection
- - Demographics form validation
- - Email field validation
- - Configuration constants
- - Identity color array validation

### Frontend Tutorial (`frontend/tutorial.test.js`)
- - Tutorial state management
- - Tutorial banner UI rendering
- - Step navigation (next/previous)
- - Step counter functionality
- - Element highlighting
- - Tutorial completion flow
- - Submit button control during tutorial

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
- - Backend: ~47% (516 statements, 275 missing)
- - Frontend: Unit tests for validation and tutorial logic
- - Data retrieval functions
- - Session management
- - Route access control

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

1. Create new test file: `tests/frontend/yourfeature.test.js`
2. Import from `@jest/globals`
3. Set up clean DOM in `beforeEach()`
4. Follow naming convention: `test('description', () => {...})`

Example:
```javascript
const { describe, test, expect, beforeEach } = require('@jest/globals');

describe('My Feature', () => {
    beforeEach(() => {
        document.body.innerHTML = `<div id="test">Hello</div>`;
    });

    test('element exists', () => {
        const el = document.getElementById('test');
        expect(el).toBeTruthy();
        expect(el.textContent).toBe('Hello');
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
- Configuration: `package.json` (jest section)
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
open coverage/lcov-report/index.html
```

## Continuous Improvement

Future test additions:
- [ ] End-to-end tests using Playwright
- [ ] API integration tests
- [ ] Database migration tests
- [ ] Performance/load tests
- [ ] Accessibility tests
- [ ] Cross-browser compatibility tests
