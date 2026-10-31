"""The intake form's own rules, enforced by the app and not only by the browser.

Measured on d4018a7: `POST /api/submit_demographics {"email": "skipall@example.com"}` returned
success, `check_demographics` said submitted, and a trial was served - past 8 required fields and
the consent box. The same POST stored an undeclared select value, a nested JSON object and a
40,000-character cell.
"""
import pytest
import yaml

from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']

DEMOGRAPHICS = [
    {'name': 'email', 'type': 'email', 'label': 'Email', 'required': True},
    {'name': 'role', 'type': 'select', 'label': 'Role', 'required': True,
     'options': [{'value': 'designer', 'label': 'Designer'}, {'value': 'researcher',
                                                                 'label': 'Researcher'}]},
    {'name': 'years', 'type': 'radio', 'label': 'Years', 'required': True,
     'options': [{'value': '1-3', 'label': '1-3'}, {'value': '4+', 'label': '4+'}]},
    {'name': 'tools', 'type': 'checkbox', 'label': 'Tools',
     'options': [{'value': 'sd', 'label': 'SD'}, {'value': 'midjourney', 'label': 'MJ'}]},
    {'name': 'notes', 'type': 'text', 'label': 'Notes'},
]

COMPLETE = {'email': 'a@b.co', 'role': 'designer', 'years': '4+',
            'tools': ['sd', 'midjourney'], 'notes': 'fine'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Intake', 'pairs_per_user': 1},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?'}],
        'demographics': DEMOGRAPHICS,
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
    return client


def test_the_intake_the_page_sends_is_accepted(client):
    reply = client.post('/api/submit_demographics', json=COMPLETE)
    assert reply.status_code == 200, reply.get_json()
    assert client.get('/api/check_demographics').get_json()['submitted'] is True
    assert client.get('/api/get_image_pair/0').status_code == 200


@pytest.mark.parametrize('field', ['email', 'role', 'years'])
def test_a_missing_required_field_is_refused_by_name(client, field):
    data = {k: v for k, v in COMPLETE.items() if k != field}
    reply = client.post('/api/submit_demographics', json=data)
    assert reply.status_code == 400
    assert field in reply.get_json()['error']
    assert client.get('/api/check_demographics').get_json()['submitted'] is False
    assert client.get('/api/get_image_pair/0').status_code != 200, 'no trials behind a refused intake'


def test_blank_does_not_satisfy_a_required_field(client):
    reply = client.post('/api/submit_demographics', json={**COMPLETE, 'role': '   '})
    assert reply.status_code == 400
    assert 'role' in reply.get_json()['error']


def test_a_select_answer_the_config_never_offered_is_refused(client):
    reply = client.post('/api/submit_demographics', json={**COMPLETE, 'role': 'wizard'})
    assert reply.status_code == 400
    assert 'role' in reply.get_json()['error']


def test_a_checkbox_answer_outside_the_declared_options_is_refused(client):
    reply = client.post('/api/submit_demographics', json={**COMPLETE, 'tools': ['sd', 'dalle']})
    assert reply.status_code == 400
    assert 'tools' in reply.get_json()['error']


def test_a_nested_object_is_not_an_answer(client):
    reply = client.post('/api/submit_demographics', json={**COMPLETE, 'notes': {'deep': 'down'}})
    assert reply.status_code == 400
    assert 'notes' in reply.get_json()['error']


def test_a_forty_thousand_character_cell_is_not_an_answer(client):
    reply = client.post('/api/submit_demographics', json={**COMPLETE, 'notes': 'x' * 40000})
    assert reply.status_code == 400
    assert 'notes' in reply.get_json()['error']


def test_a_body_that_is_not_an_object_is_refused(client):
    assert client.post('/api/submit_demographics', json=[1, 2]).status_code == 400


def test_an_optional_field_may_be_left_out(client):
    data = {k: v for k, v in COMPLETE.items() if k != 'notes'}
    assert client.post('/api/submit_demographics', json=data).status_code == 200


def test_a_key_the_study_never_declared_is_not_part_of_the_intake(client):
    """The roster spreads the stored demographics blob, so an undeclared key becomes a roster field."""
    payload = {**COMPLETE, 'junk': {'deep': 'down'}, 'blob': 'x' * 40000}
    assert client.post('/api/submit_demographics', json=payload).status_code == 200
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    row = client.get('/api/admin/participants').get_json()['rows'][0]

    assert 'junk' not in row and 'blob' not in row, 'intake keys the study never declared were stored'
    assert row['notes'] == COMPLETE['notes']
