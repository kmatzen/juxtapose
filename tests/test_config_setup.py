"""Documented-setup-path regressions: the config the README describes must actually boot."""
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The README's six required keys, nothing else. No layout section: the README never documents one.
MINIMAL_CONFIG = """
survey:
  title: "Layout-free study"
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - name: prompt
    type: text
    column: prompt
outputs:
  - name: image
    type: image
    column_a: image_a_url
    column_b: image_b_url
questions:
  - name: image_quality
    type: ab_preference
    label: "Which looks better?"
"""

# Empty trailing fields are the optional mask/identity columns: the shape audit #5 is about.
MINIMAL_TSV = "a prompt\tMethod-A\tMethod-B\thttps://x/a.png\thttps://x/b.png\t\t\n"


def write_minimal_setup(tmp_path):
    config_path = tmp_path / 'survey_config.yaml'
    config_path.write_text(MINIMAL_CONFIG, encoding='utf-8')
    # Absolute path wins over the repo-root-relative resolution in _load_trials_from_file.
    pairs_path = tmp_path / 'pairs.tsv'
    pairs_path.write_text(MINIMAL_TSV, encoding='utf-8')
    return str(config_path), str(pairs_path)


def test_load_config_accepts_config_without_layout(tmp_path):
    from src.survey.config import load_config

    config_path, _ = write_minimal_setup(tmp_path)
    config = load_config(config_path)

    assert 'layout' not in config
    assert config['questions'][0]['name'] == 'image_quality'


def test_app_imports_with_readme_minimal_config(tmp_path):
    config_path, pairs_path = write_minimal_setup(tmp_path)
    env = dict(os.environ)
    env.update({
        'SURVEY_CONFIG': config_path,
        'IMAGE_PAIRS_FILE': pairs_path,
        'APP_ENV': 'production',
        'RATELIMIT_STORAGE_URI': 'redis://limiter.test:6379/0',

        'DATA_DIR': str(tmp_path),
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'ADMIN_PASSWORD': 'a-real-password-for-this-test',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })

    result = subprocess.run(
        [sys.executable, '-c', 'import src.survey.app; print("booted")'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'booted' in result.stdout


def run_generator(tmp_path):
    generated = subprocess.run(
        [sys.executable, str(REPO_ROOT / 'generate_pairs.py')],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert generated.returncode == 0, generated.stderr
    pairs_path = tmp_path / 'generated.tsv'
    pairs_path.write_text(generated.stdout, encoding='utf-8')
    return str(pairs_path)


def test_generate_pairs_output_loads_without_skips(tmp_path, caplog):
    """Rows from the documented generator must survive the loader's column check."""
    pairs_path = run_generator(tmp_path)

    from src.survey import app as app_module
    with caplog.at_level(logging.WARNING, logger='src.survey.app'):
        trials = app_module._load_trials_from_file(pairs_path)

    skipped = [r.getMessage() for r in caplog.records if 'skipping' in r.getMessage()]
    assert skipped == []
    assert len(trials) == 9
    assert trials[0]['method_a'] == 'Method-A'
    assert trials[0]['prompt'] == 'A serene mountain landscape at sunset'


def test_missing_data_file_raises_naming_the_path(tmp_path):
    """A missing data file must not be replaced by placeholder trials."""
    from src.survey import app as app_module

    missing = str(tmp_path / 'no_such_study.tsv')
    with pytest.raises(FileNotFoundError) as excinfo:
        app_module._load_trials_from_file(missing)

    assert 'no_such_study.tsv' in str(excinfo.value)
    assert not os.path.exists(missing)


def test_missing_data_file_fails_startup_without_writing_samples(tmp_path):
    """Startup must fail, not author a study out of placeholder rows."""
    config_path, _ = write_minimal_setup(tmp_path)
    env = dict(os.environ)
    env.update({
        'SURVEY_CONFIG': config_path,
        'IMAGE_PAIRS_FILE': str(tmp_path / 'definitely_missing.tsv'),
        'APP_ENV': 'production',
        'RATELIMIT_STORAGE_URI': 'redis://limiter.test:6379/0',

        'DATA_DIR': str(tmp_path),
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'ADMIN_PASSWORD': 'a-real-password-for-this-test',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })

    result = subprocess.run(
        [sys.executable, '-c', 'import src.survey.app'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert 'definitely_missing.tsv' in result.stderr
    assert list(REPO_ROOT.glob('sample-*')) == []


def test_app_boots_on_generated_pairs_file(tmp_path):
    """The generator is the documented way to create a study's data file."""
    config_path, _ = write_minimal_setup(tmp_path)
    env = dict(os.environ)
    env.update({
        'SURVEY_CONFIG': config_path,
        'IMAGE_PAIRS_FILE': run_generator(tmp_path),
        'APP_ENV': 'production',
        'RATELIMIT_STORAGE_URI': 'redis://limiter.test:6379/0',

        'DATA_DIR': str(tmp_path),
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'ADMIN_PASSWORD': 'a-real-password-for-this-test',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })

    result = subprocess.run(
        [sys.executable, '-c',
         'import src.survey.app as a; print(f"booted {a.IMAGE_PAIRS.count} trials")'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'booted 9 trials' in result.stdout
