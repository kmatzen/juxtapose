"""Audit F2: the mode that decides which security gates are on must be stated, not inferred.

IS_PRODUCTION used to be bool(DATA_DIR): deploy with the results volume mounted at an unexpected
path, DATA_DIR is empty, and the app boots happily with the dev secret key, the admin123 password and
dev-mode sessions - failing open, silently. These tests run the real import in a subprocess, because
the gates fire at import and pytest has already imported the module in this process.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The gates read the environment as a whole, so the child starts from a clean room.
STRIPPED = ('APP_ENV', 'SECRET_KEY', 'ADMIN_PASSWORD', 'DATA_DIR')


def boot(**env):
    child = {k: v for k, v in os.environ.items() if k not in STRIPPED}
    child['PYTHONPATH'] = str(ROOT)
    child.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        [sys.executable, '-c', 'import src.survey.app'],
        cwd=ROOT, env=child, capture_output=True, text=True, timeout=180,
    )


PRODUCTION_SECRETS = {'SECRET_KEY': 'a' * 32, 'ADMIN_PASSWORD': 'b' * 16}


def test_the_app_refuses_to_start_without_app_env():
    result = boot()
    assert result.returncode != 0, 'the app started with APP_ENV unset: mode, and so every gate, was guessed'
    assert 'APP_ENV' in result.stderr


def test_production_without_a_secret_key_refuses_to_start():
    result = boot(APP_ENV='production', ADMIN_PASSWORD='b' * 16)
    assert result.returncode != 0 and 'SECRET_KEY' in result.stderr


def test_production_without_an_admin_password_refuses_to_start():
    result = boot(APP_ENV='production', SECRET_KEY='a' * 32)
    assert result.returncode != 0 and 'ADMIN_PASSWORD' in result.stderr


def test_production_with_the_required_secrets_starts(tmp_path):
    result = boot(APP_ENV='production', DATA_DIR=tmp_path, **PRODUCTION_SECRETS)
    assert result.returncode == 0, result.stderr


def test_dev_starts_without_secrets():
    result = boot(APP_ENV='dev')
    assert result.returncode == 0, result.stderr


def test_an_unrecognised_mode_refuses_to_start():
    result = boot(APP_ENV='stagign')
    assert result.returncode != 0 and 'APP_ENV' in result.stderr


def test_production_refuses_dev_mode(tmp_path):
    """DEV_MODE bypasses referral codes, cuts the pair count and turns on answer autofill."""
    result = boot(APP_ENV='production', DEV_MODE='true', DATA_DIR=tmp_path, **PRODUCTION_SECRETS)
    assert result.returncode != 0 and 'DEV_MODE' in result.stderr
