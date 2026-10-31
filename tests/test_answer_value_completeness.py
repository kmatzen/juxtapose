"""A rating question is answered when its value is there, not when an answer object exists.

Measured on d4018a7: a study with a required likert and a required multiple choice, answered
`{"value": null}` for both, returned `completed: true`, progress 1, and the next pair 404'd - the
participant finished the study having rated nothing.
"""
import json

import pytest
import yaml

from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Ratings', 'pairs_per_user': 1},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [
            {'name': 'quality', 'type': 'ab_preference', 'label': 'Which?',
             'required': True, 'confidence': True},
            {'name': 'rating', 'type': 'likert', 'label': 'Rate 1-5',
             'required': True, 'scale': 5},
            {'name': 'which', 'type': 'multiple_choice', 'label': 'Pick', 'required': True,
             'options': [{'value': 'x', 'label': 'X'}, {'value': 'y', 'label': 'Y'}]},
        ],
    }
    (tmp_path / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    row = '\t'.join(['a prompt', 'A', 'B', 'https://x/a.png', 'https://x/b.png', '', ''])
    (tmp_path / 'pairs.tsv').write_text(row + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    client = app.test_client()
    client.get('/')
    client.post('/api/submit_demographics', json={'email': 'r@example.com', 'consent': 'yes'})
    return client


def _post(client, responses):
    pair = client.get('/api/get_image_pair/0').get_json()
    return client.post('/api/submit_survey',
                       json={'image_pair_id': pair['id'], 'responses': responses,
                             'time_spent': 12})


def test_an_empty_rating_does_not_finish_the_trial(client):
    reply = _post(client, {'quality': {'choice': 'A', 'confidence': 4},
                           'rating': {'value': None},
                           'which': {'value': None}}).get_json()
    assert reply['success'] is True
    assert reply['completed'] is False, 'an empty rating and an empty pick are unanswered'
    assert client.get('/api/check_demographics').get_json()['completed_pairs'] == 0
    assert client.get('/api/get_image_pair/0').status_code == 200, 'the trial is still owed'


def test_a_real_rating_finishes_the_trial(client):
    reply = _post(client, {'quality': {'choice': 'A', 'confidence': 4},
                           'rating': {'value': 3},
                           'which': {'value': 'x'}}).get_json()
    assert reply['completed'] is True
    assert client.get('/api/check_demographics').get_json()['completed_pairs'] == 1
