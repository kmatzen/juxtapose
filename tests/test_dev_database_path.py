"""Audit F12: a dev run wrote survey.db into the app's own directory.

The production path is DATA_DIR/survey.db. The fallback was the bare filename, so a local run - and,
before F2, a deployment that forgot DATA_DIR - wrote a study database inside the source tree, where
it is one `git clean -fdx` away from being deleted and one `git add -A` away from being committed.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _database(**env):
    child = {k: v for k, v in os.environ.items() if k not in ('DATA_DIR', 'APP_ENV')}
    child['PYTHONPATH'] = str(ROOT)
    child['APP_ENV'] = 'dev'
    child.update({k: str(v) for k, v in env.items()})
    result = subprocess.run(
        [sys.executable, '-c', 'from src.survey import app; print(app.DATABASE)'],
        cwd=ROOT, env=child, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_a_dev_run_writes_its_database_outside_the_repo():
    database = _database()
    assert database, 'no database path resolved'
    assert not Path(database).resolve().is_relative_to(ROOT), \
        f'the dev database lives in the source tree: {database}'


def test_production_still_uses_the_data_dir(tmp_path):
    database = _database(APP_ENV='production', DATA_DIR=tmp_path,
                         SECRET_KEY='a' * 32, ADMIN_PASSWORD='b' * 16,
                         RATELIMIT_STORAGE_URI='redis://limiter.test:6379/0')
    assert database == str(tmp_path / 'survey.db')
