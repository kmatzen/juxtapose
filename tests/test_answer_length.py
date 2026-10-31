"""Intake cells are capped at 2,000 characters; answers are not capped at all.

Measured on 156fe69: a 55,000-character free-text answer is accepted (the 64 KB request ceiling is
the only limit), the dashboard's 3-row page for it is 167 KB and the CSV 166 KB, and the page posts
it happily because the textarea carries no `maxlength`. The dashboard re-fetches its page every 30
seconds, so one participant pasting a novel makes the analyst's poll ship megabytes.
"""
import pytest
import yaml

from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']
LIMIT = 2000


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Length', 'pairs_per_user': 2},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?',
                       'confidence': True},
                      {'name': 'comment', 'type': 'free_text', 'label': 'Notes'}],
        'demographics': [{'name': 'email', 'type': 'email', 'label': 'Email', 'required': True},
                         {'name': 'notes', 'type': 'textarea', 'label': 'Anything else?'}],
    }
    (tmp_path / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    row = '\t'.join(['a prompt', 'A', 'B', 'https://x/a.png', 'https://x/b.png', '', ''])
    (tmp_path / 'pairs.tsv').write_text(row + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    test_client = app.test_client()
    test_client.get('/')
    test_client.post('/api/submit_demographics', json={'email': 'long@example.com',
                                                       'consent': 'yes'})
    return test_client


def _answer(client, text):
    served = client.get('/api/get_image_pair/0').get_json()
    return client.post('/api/submit_survey', json={
        'image_pair_id': served['id'],
        'responses': {'quality': {'choice': 'A', 'confidence': 4}, 'comment': {'text': text}},
        'time_spent': 12})


@pytest.mark.parametrize('size', [LIMIT + 1, 55000])
def test_an_answer_longer_than_an_intake_cell_is_refused_by_name(client, size):
    response = _answer(client, 'x' * size)
    assert response.status_code == 400, response.get_json()
    assert 'comment' in response.get_json()['error']
    assert str(LIMIT) in response.get_json()['error']


def test_an_answer_the_intake_would_have_accepted_is_accepted(client):
    response = _answer(client, 'x' * LIMIT)
    assert response.status_code == 200, response.get_json()


def test_the_answer_box_stops_the_novel_before_the_request_does(client):
    page = client.get('/').get_data(as_text=True)
    boxes = [line for line in page.splitlines() if 'name="comment_text"' in line]
    assert boxes, 'the free-text question renders a textarea'
    assert all('maxlength' in box for box in boxes), boxes


def test_the_intake_box_is_capped_by_the_page_too(client):
    page = client.get('/').get_data(as_text=True)
    boxes = [line for line in page.splitlines() if 'name="notes"' in line and '<textarea' in line]
    assert boxes, 'the textarea demographics field renders a textarea'
    assert all('maxlength' in box for box in boxes), boxes
