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
    # Absolute path wins over the repo-root-relative resolution in TrialStore.
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
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
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
        store = app_module.TrialStore(pairs_path)

    skipped = [r.getMessage() for r in caplog.records if 'skipping' in r.getMessage()]
    assert skipped == []
    assert store.count == 9
    first = store.get(store.ids[0])
    assert first['method_a'] == 'Method-A'
    assert first['prompt'] == 'A serene mountain landscape at sunset'


def test_missing_data_file_raises_naming_the_path(tmp_path):
    """A missing data file must not be replaced by placeholder trials."""
    from src.survey import app as app_module

    missing = str(tmp_path / 'no_such_study.tsv')
    with pytest.raises(FileNotFoundError) as excinfo:
        app_module.TrialStore(missing)

    assert 'no_such_study.tsv' in str(excinfo.value)
    assert not os.path.exists(missing)


def test_missing_data_file_fails_startup_without_writing_samples(tmp_path):
    """Startup must fail, not author a study out of placeholder rows."""
    config_path, _ = write_minimal_setup(tmp_path)
    env = dict(os.environ)
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
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
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
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


def _boot_show_prompt(tmp_path, extra_env):
    """Import the app in a child process and report the flag that decides whether the prompt box renders."""
    config_path, pairs_path = write_minimal_setup(tmp_path)  # this config HAS a prompt text input
    env = dict(os.environ)
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
    env.update({
        'APP_ENV': 'dev',
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'ADMIN_PASSWORD': 'a-real-password-for-this-test',
        'SURVEY_CONFIG': config_path,
        'IMAGE_PAIRS_FILE': pairs_path,
        'PYTHONPATH': os.pathsep.join(sys.path),
    })
    env.update(extra_env)

    result = subprocess.run(
        [sys.executable, '-c', 'from src.survey import app; print(app.SHOW_PROMPT)'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_the_environment_cannot_override_what_the_study_config_decides(tmp_path):
    """SHOW_PROMPT / ENABLE_PROMPT_QUESTION mirrored config-derived values, so a deployment could
    render a prompt box for a study whose config has no prompt input, or hide the prompt of a study
    that has one. The config describes the study; the environment does not."""
    assert _boot_show_prompt(tmp_path, {}) == 'True'
    assert _boot_show_prompt(tmp_path, {'SHOW_PROMPT': 'false'}) == 'True', \
        'SHOW_PROMPT still overrides what the config says'


# --- Audit #10: a config that cannot serve a trial must be refused at boot, not at the first participant.

def write_config(tmp_path, text):
    """The minimal study with one key removed from one entry."""
    (tmp_path / 'survey_config.yaml').write_text(text, encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(MINIMAL_TSV, encoding='utf-8')
    return str(tmp_path / 'survey_config.yaml')


def test_an_input_that_names_no_column_is_refused(tmp_path):
    from src.survey.config import load_config

    path = write_config(tmp_path, MINIMAL_CONFIG.replace('    column: prompt\n', ''))

    with pytest.raises(ValueError, match='column'):
        load_config(path)


def test_an_output_that_names_only_one_of_its_columns_is_refused(tmp_path):
    from src.survey.config import load_config

    path = write_config(tmp_path, MINIMAL_CONFIG.replace('    column_b: image_b_url\n', ''))

    with pytest.raises(ValueError, match='column_b'):
        load_config(path)


def test_a_question_with_no_type_is_refused_by_name(tmp_path):
    """A question without a type reaches _apply_defaults' q['type'] and 500s the boot with a bare KeyError."""
    from src.survey.config import load_config

    path = write_config(tmp_path, MINIMAL_CONFIG.replace('    type: ab_preference\n', ''))

    with pytest.raises(ValueError, match='image_quality'):
        load_config(path)


def test_a_config_missing_a_column_refuses_to_boot(tmp_path):
    """The README's setup guide ends at `flask run`, so the refusal has to be the app's, not the loader's."""
    write_config(tmp_path, MINIMAL_CONFIG.replace('    column: prompt\n', ''))
    env = dict(os.environ)
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
    env.update({
        'SURVEY_CONFIG': str(tmp_path / 'survey_config.yaml'),
        'IMAGE_PAIRS_FILE': str(tmp_path / 'pairs.tsv'),
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
    assert 'column' in result.stderr
