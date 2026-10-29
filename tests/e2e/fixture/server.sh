#!/usr/bin/env bash
# Boot the app against the generated browser-test fixture. Playwright's webServer owns it.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="${E2E_RUN_DIR:-${TMPDIR:-/tmp}/juxtapose-e2e}"
PYTHON="${PYTHON:-/tmp/jlvenv/bin/python}"
# The dev venv is not everywhere: fall back to the interpreter CI installed the app into.
[ -x "$PYTHON" ] || PYTHON=python3
ROWS="${E2E_ROWS:-4}"
PORT="${PORT:-5055}"

"$PYTHON" "$REPO/tests/e2e/fixture/make_run.py" "$RUN" "$ROWS"

cd "$RUN"
export PYTHONPATH="$REPO"
export E2E_RUN_DIR="$RUN"
export DATA_DIR="$RUN"
export SURVEY_CONFIG="$RUN/survey_config.yaml"
export IMAGE_PAIRS_FILE="$RUN/trials.tsv"
export TUTORIAL_PAIRS_FILE="$RUN/tutorial_image_pair.txt"
export SECRET_KEY="${SECRET_KEY:-e2e-secret-key}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-e2e-admin-password}"
export DEV_MODE=false
export PORT="$PORT"

exec "$PYTHON" "$REPO/tests/e2e/fixture/serve.py"
