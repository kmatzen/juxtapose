# Contributing to Juxtapose

Thanks for your interest in improving Juxtapose! This guide covers local setup
and running the test suites.

## Setup

Requires Python 3.11+ and Node 20+.

```bash
# Python app + dev dependencies
pip install -e ".[dev]"

# Frontend test dependencies
npm ci
```

Copy `.env.example` to `.env` and fill in values for local runs. In development
you can simply run:

```bash
DEV_MODE=true python -m src.survey.app
```

## Running tests

```bash
# Python (Flask) tests
python -m pytest tests/ -q

# Frontend (jest) tests
npm test
```

Both suites also run in CI (`.github/workflows/ci.yml`) on every push and pull
request.

### Troubleshooting

- **`pip install` fails to uninstall `blinker`** ("RECORD file not found"): this
  happens when a system package manager owns `blinker`. Work around it with
  `pip install -e ".[dev]" --ignore-installed blinker`. Clean CI runners are
  usually unaffected.

## Pull requests

- Keep changes focused and include tests for behavior changes.
- Make sure both test suites pass locally before opening a PR.
