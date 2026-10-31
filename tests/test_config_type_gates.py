"""A `type` is a render instruction, so a typo in one is a study that cannot be run.

Measured on 156fe69: a required question `type: likert5` booted, rendered a section with 0 answer
widgets, and every trial answered `{"completed": false}` - the participant was handed the study
again and could never finish. A required intake field `type: dropdown` booted, rendered 0 widgets,
and the intake came back `400 Field 'role' is required`, so the first pair request answered
`403 Demographics not submitted` and nobody could start. An input `type: galery` booted, the
front end's `inputOfType('image_gallery')` returned null, and the study ran with the reference
images silently missing. The gate already refuses a choice question with no options and a quoted
`scale`; a misspelled type is the same class of mistake.
"""
from pathlib import Path

import pytest
import yaml

from src.survey.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE = yaml.safe_load("""
survey:
  title: "Types"
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - {name: prompt, type: text, column: prompt}
  - {name: mask, type: image, column: mask_url, optional: true}
  - {name: identity, type: image_gallery, column: identity_urls, optional: true}
outputs:
  - {name: image, type: image, column_a: image_a_url, column_b: image_b_url}
questions:
  - {name: image_quality, type: ab_preference, label: "Which?"}
  - {name: prompt_adherence, type: likert, label: "Faithful?", scale: 5}
  - {name: notes, type: free_text, label: "Notes"}
  - {name: device, type: multiple_choice, label: "Viewed on", options: [{value: d, label: Desktop}]}
demographics:
  - {name: email, type: email, label: "Email", required: true}
""")


def _load(tmp_path: Path, mutate) -> dict:
    config = yaml.safe_load(yaml.safe_dump(BASE))
    mutate(config)
    path = tmp_path / 'survey_config.yaml'
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return load_config(str(path))


def test_a_question_type_the_page_does_not_render_is_refused(tmp_path):
    with pytest.raises(ValueError, match='likert5'):
        _load(tmp_path, lambda c: c['questions'][1].update(type='likert5'))


def test_a_demographics_type_the_page_does_not_render_is_refused(tmp_path):
    with pytest.raises(ValueError, match='dropdown'):
        _load(tmp_path, lambda c: c['demographics'].append(
            {'name': 'role', 'type': 'dropdown', 'label': 'Role',
             'options': [{'value': 'd', 'label': 'Designer'}]}))


def test_an_input_type_the_page_does_not_render_is_refused(tmp_path):
    with pytest.raises(ValueError, match='galery'):
        _load(tmp_path, lambda c: c['inputs'].append(
            {'name': 'gallery', 'type': 'galery', 'column': 'identity_urls'}))


def test_the_refusal_names_the_entry_it_refused(tmp_path):
    with pytest.raises(ValueError, match='prompt_adherence'):
        _load(tmp_path, lambda c: c['questions'][1].update(type='likert5'))


def test_every_type_the_page_renders_is_accepted(tmp_path):
    """The allow-list must not be tighter than the template and the components."""
    config = _load(tmp_path, lambda c: c['demographics'].extend([
        {'name': 'name', 'type': 'text', 'label': 'Name'},
        {'name': 'age', 'type': 'number', 'label': 'Age'},
        {'name': 'comments', 'type': 'textarea', 'label': 'Anything else?'},
        {'name': 'occupation', 'type': 'select', 'label': 'Role',
         'options': [{'value': 'r', 'label': 'Researcher'}]},
        {'name': 'seniority', 'type': 'radio', 'label': 'Seniority',
         'options': [{'value': 'j', 'label': 'Junior'}]},
        {'name': 'tools', 'type': 'checkbox', 'label': 'Tools',
         'options': [{'value': 'sd', 'label': 'Stable Diffusion'}]},
    ]))
    assert len(config['questions']) == 4
    assert len(config['inputs']) == 3
    assert len(config['demographics']) == 7


def test_the_shipped_study_still_boots():
    assert load_config(str(REPO_ROOT / 'survey_config.yaml'))['survey']['title']
