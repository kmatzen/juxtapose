"""F14 (fifth audit): the parser resolved a data column through the input *name* before the input's
own column, so a study that names an input after another input's column applied the wrong `optional`
flag to a blank cell - the empty tile value was stored as '' and counted as an answered column.

The lookup lived in INPUTS_BY_NAME, built when the module is imported, so this study has to be
booted, not monkeypatched: a patched CONFIG never reaches the name-first lookup.
"""
import importlib

import pytest

CONFIG = """
survey:
  title: "Name collision study"
  pairs_per_user: 1
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - name: mask
    type: image
    column: mask_url
    optional: true
  - name: mask_url
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
    scale: 5
"""

ROW = ['a prompt', 'Method-A', 'Method-B', 'a.png', 'b.png', '', '']


@pytest.fixture
def colliding_app(tmp_path, monkeypatch):
    config = tmp_path / 'survey_config.yaml'
    config.write_text(CONFIG, encoding='utf-8')
    pairs = tmp_path / 'pairs.tsv'
    pairs.write_text('\t'.join(ROW) + '\n', encoding='utf-8')
    monkeypatch.setenv('SURVEY_CONFIG', str(config))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(pairs))
    monkeypatch.setenv('APP_ENV', 'dev')

    from src.survey import app as app_module
    importlib.reload(app_module)
    return app_module


def test_a_blank_optional_cell_stays_absent_when_an_input_is_named_after_the_column(colliding_app):
    row = colliding_app._parse_trial_line(ROW, colliding_app.CONFIG['data']['columns'], 1)

    assert row['mask_url'] is None, (
        f"the blank mask_url cell parsed to {row['mask_url']!r}: the optional flag was read from the "
        "input *named* mask_url, not from the input whose column is mask_url")
