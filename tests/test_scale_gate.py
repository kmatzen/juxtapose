"""F10: `scale` was the one config value the boot gate did not refuse, and a quoted one is fatal.

`index.html` renders the likert scale with `{% for i in range(1, q.scale + 1) %}`. `scale: "5"` is
valid YAML, passes the loader, and then raises TypeError inside the template: every page render 500s,
on a study that booted happily. The boot gate is where that belongs.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_CONFIG = """
survey:
  title: "Scale study"
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
  - name: rating
    type: likert
    label: "How natural does it look?"
    scale: {scale}
"""

PAIRS = "a prompt\tMethod-A\tMethod-B\thttps://x/a.png\thttps://x/b.png\t\t\n"


def write_study(tmp_path, scale):
    config_path = tmp_path / 'survey_config.yaml'
    config_path.write_text(BASE_CONFIG.format(scale=scale), encoding='utf-8')
    pairs_path = tmp_path / 'pairs.tsv'
    pairs_path.write_text(PAIRS, encoding='utf-8')
    return config_path, pairs_path


def boot(tmp_path, scale):
    """A real import in a fresh process: the boot gate is a boot-time behaviour, not a function."""
    config_path, pairs_path = write_study(tmp_path, scale)
    env = dict(os.environ)
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
    env.update({
        'SURVEY_CONFIG': str(config_path),
        'IMAGE_PAIRS_FILE': str(pairs_path),
        'APP_ENV': 'dev',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })
    return subprocess.run(
        [sys.executable, '-c', 'import src.survey.app; print("booted")'],
        env=env, cwd=str(REPO_ROOT), capture_output=True, text=True,
    )


@pytest.mark.parametrize('scale', ['"5"', 'five', '1.5', 'true'])
def test_a_scale_that_is_not_a_number_refuses_to_boot(tmp_path, scale):
    result = boot(tmp_path, scale)

    assert result.returncode != 0, (
        f'scale: {scale} booted, and every page render 500s on the template that counts to it')
    assert 'rating' in result.stderr, f'the refusal must name the question, got: {result.stderr[-300:]}'
    assert 'scale' in result.stderr


def test_a_real_scale_still_boots(tmp_path):
    result = boot(tmp_path, '7')

    assert result.returncode == 0, result.stderr
    assert 'booted' in result.stdout


def test_the_loader_names_the_question_and_the_value(tmp_path):
    from src.survey.config import load_config

    config_path, _ = write_study(tmp_path, '"5"')
    with pytest.raises(ValueError) as raised:
        load_config(str(config_path))

    assert 'rating' in str(raised.value) and 'scale' in str(raised.value)


def test_the_likert_scale_defaults_to_five(tmp_path):
    """The gate must not move the default: an omitted scale is still 5."""
    from src.survey.config import load_config

    config_path, _ = write_study(tmp_path, '5')
    assert load_config(str(config_path))['questions'][0]['scale'] == 5
