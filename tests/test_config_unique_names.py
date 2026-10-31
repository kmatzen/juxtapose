"""Config names are JSON keys, CSV columns and DOM ids at once, so a repeated one deletes data.

Measured on d4018a7: a study with two questions named `image_quality` booted, the participant
answered both (A/5 and B/1), and the stored row kept one entry. Nothing said so.
"""
from pathlib import Path

import pytest
import yaml

from src.survey.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE = yaml.safe_load("""
survey:
  title: "Names"
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - {name: prompt, type: text, column: prompt}
  - {name: mask, type: image, column: mask_url, optional: true}
outputs:
  - {name: image, type: image, column_a: image_a_url, column_b: image_b_url}
questions:
  - {name: image_quality, type: ab_preference, label: "Which?"}
  - {name: prompt_adherence, type: ab_preference, label: "Faithful?"}
demographics:
  - {name: email, type: email, label: "Email", required: true}
  - {name: occupation, type: select, label: "Role", options: [{value: r, label: R}]}
""")


def _load(tmp_path: Path, mutate) -> dict:
    config = yaml.safe_load(yaml.safe_dump(BASE))
    mutate(config)
    path = tmp_path / 'survey_config.yaml'
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return load_config(str(path))


def test_two_questions_with_one_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match='image_quality'):
        _load(tmp_path, lambda c: c['questions'][1].update(name='image_quality'))


def test_two_demographics_fields_with_one_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match='occupation'):
        _load(tmp_path, lambda c: c['demographics'].append(
            {'name': 'occupation', 'type': 'text', 'label': 'Other role'}))


def test_two_inputs_with_one_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match='mask'):
        _load(tmp_path, lambda c: c['inputs'].append(
            {'name': 'mask', 'type': 'image', 'column': 'image_a_url', 'optional': True}))


def test_two_outputs_with_one_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match='image'):
        _load(tmp_path, lambda c: c['outputs'].append(
            {'name': 'image', 'type': 'text', 'column_a': 'prompt', 'column_b': 'method_a'}))


def test_a_column_named_twice_is_refused(tmp_path):
    # _parse_trial_line writes row[col] per index, so the second cell silently wins.
    def mutate(c):
        c['data']['columns'].append('prompt')
        c['inputs'].append({'name': 'extra', 'type': 'text', 'column': 'prompt'})
    with pytest.raises(ValueError, match='prompt'):
        _load(tmp_path, mutate)


def test_the_shipped_study_still_boots():
    assert load_config(str(REPO_ROOT / 'survey_config.yaml'))['survey']['title']
