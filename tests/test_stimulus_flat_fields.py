"""Eighth audit F10: the submit path writes the trial counters and pops them straight back out.

Measured on 1e47f6f: `_add_flat_fields()` ends every call with `stim['total_pairs'] =
stim.get('total_trials', 0)`, so `submit_survey` spends three lines popping `total_trials` and
`total_pairs` off the dict it built one line earlier. The counters describe the trial the server is
*serving*, not an answer being stored, and the function has no way to be told the difference.
"""
import json

import pytest
import yaml

from src.survey import app as app_module
from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']


@pytest.fixture
def app(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Counters', 'pairs_per_user': 2},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?',
                       'confidence': True}],
        'demographics': [{'name': 'email', 'type': 'email', 'label': 'Email', 'required': True}],
    }
    (tmp_path / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    rows = ['\t'.join([f'prompt {n}', 'A', 'B', f'https://x/{n}a.png', f'https://x/{n}b.png', '', ''])
            for n in ('a', 'b')]
    (tmp_path / 'pairs.tsv').write_text('\n'.join(rows) + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    return _boot_app(tmp_path, monkeypatch, csrf_enabled=False)


def _participant(app):
    client = app.test_client()
    client.get('/')
    posted = client.post('/api/submit_demographics',
                         json={'email': 'counters@lab.example', 'consent': 'yes'})
    assert posted.status_code == 200, posted.get_json()
    return client


def _stored_blob(client):
    with client.application.app_context():
        db = app_module.get_db()
        try:
            raw = db.execute('SELECT stimulus_data FROM survey_responses').fetchone()
        finally:
            db.close()
    assert raw is not None, 'the answer did not reach the database'
    return json.loads(raw['stimulus_data'])


def test_the_served_trial_carries_both_counters(app):
    served = _participant(app).get('/api/get_image_pair/0').get_json()

    assert served['total_trials'] == 2
    assert served['total_pairs'] == 2


def test_a_stored_answer_carries_neither_counter(app):
    client = _participant(app)
    served = client.get('/api/get_image_pair/0').get_json()
    posted = client.post('/api/submit_survey', json={
        'image_pair_id': served['id'],
        'responses': {'quality': {'choice': 'A', 'confidence': 4}},
        'time_spent': 9.5,
    })
    assert posted.status_code == 200, posted.get_json()

    blob = _stored_blob(client)
    assert 'total_trials' not in blob and 'total_pairs' not in blob
    assert blob['method_a'], 'the flat fields the JS reads are still written'


def test_add_flat_fields_can_be_asked_not_to_write_the_counters(app):
    trial = app_module.IMAGE_PAIRS.get(1)
    stim = app_module._build_stimulus_data(trial, randomized=False)
    stim['total_trials'] = 7

    app_module._add_flat_fields(stim, trial, False, include_counters=False)

    assert stim['total_trials'] == 7, 'the counters belong to the caller'
    assert 'total_pairs' not in stim
    assert stim['method_a'] == trial['method_a']
