"""`pairs_per_user` is compared with the pair count, so a YAML value that is not an int is a 500.

Measured on 156fe69: `pairs_per_user: "2"` boots, and then `min(IMAGE_PAIRS.count, "2")` raises
`TypeError: '<' not supported between instances of 'str' and 'int'` - `GET /` and
`/api/get_image_pair/0` both answer 500 and the participant sits on "Failed to load image pair".
`pairs_per_user: 0` and `-1` boot and serve the thank-you page immediately, so the study collects
nothing, and `true` runs a one-trial study. The loader already refuses a quoted `scale` for the
same reason.
"""
from pathlib import Path

import pytest
import yaml

from src.survey.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE = yaml.safe_load("""
survey:
  title: "Counts"
  pairs_per_user: 6
  dev_pairs: 3
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - {name: prompt, type: text, column: prompt}
outputs:
  - {name: image, type: image, column_a: image_a_url, column_b: image_b_url}
questions:
  - {name: image_quality, type: ab_preference, label: "Which?"}
demographics:
  - {name: email, type: email, label: "Email", required: true}
""")


def _load(tmp_path: Path, mutate) -> dict:
    config = yaml.safe_load(yaml.safe_dump(BASE))
    mutate(config)
    path = tmp_path / 'survey_config.yaml'
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return load_config(str(path))


@pytest.mark.parametrize('value', ['6', '6.0', 6.0, True, 0, -1])
def test_a_pairs_per_user_the_trial_count_cannot_use_is_refused(tmp_path, value):
    with pytest.raises(ValueError, match='pairs_per_user'):
        _load(tmp_path, lambda c: c['survey'].update(pairs_per_user=value))


def test_a_quoted_dev_pairs_is_refused(tmp_path):
    with pytest.raises(ValueError, match='dev_pairs'):
        _load(tmp_path, lambda c: c['survey'].update(dev_pairs='1'))


def test_the_refusal_names_the_value_it_refused(tmp_path):
    with pytest.raises(ValueError, match='6'):
        _load(tmp_path, lambda c: c['survey'].update(pairs_per_user='6'))


def test_real_counts_are_accepted(tmp_path):
    assert _load(tmp_path, lambda c: c['survey'].update(pairs_per_user=1))['survey']['pairs_per_user'] == 1
    assert _load(tmp_path, lambda c: c['survey'].update(pairs_per_user=500))['survey']['pairs_per_user'] == 500


def test_the_shipped_study_still_boots():
    config = load_config(str(REPO_ROOT / 'survey_config.yaml'))
    assert isinstance(config['survey']['pairs_per_user'], int)
    assert config['survey']['pairs_per_user'] >= 1
