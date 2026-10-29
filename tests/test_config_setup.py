"""Documented-setup-path regressions: the config the README describes must actually boot."""
import os
import subprocess
import sys

# The README's six required keys, nothing else. No layout section: the README never documents one.
MINIMAL_CONFIG = """
survey:
  title: "Layout-free study"
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url]
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

MINIMAL_TSV = "a prompt\tMethod-A\tMethod-B\thttps://x/a.png\thttps://x/b.png\n"


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
