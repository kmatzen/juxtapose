"""Consent has to reach the record the researcher reads, and the app has to ask for it.

Measured on d4018a7: a study with `survey.consent_text` set, a participant who ticked the box -
the export header had 46 columns and none of them said consent, and an intake with no consent key
at all was accepted. `consent` is not a demographics field, so nothing in the config put it there.
"""
import pytest
import yaml

from tests.conftest import _boot_app, complete_intake

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']


def _study(tmp_path, monkeypatch, consent_text):
    config = {
        'survey': {'title': 'Consent', 'pairs_per_user': 1, 'consent_text': consent_text},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?'}],
        'demographics': [
            {'name': 'email', 'type': 'email', 'label': 'Email', 'required': True},
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
    return client


def test_a_study_that_asks_for_consent_refuses_an_intake_without_it(tmp_path, monkeypatch):
    client = _study(tmp_path, monkeypatch, 'I agree to my answers being used in this study.')

    refused = client.post('/api/submit_demographics',
                          json={'email': 'noconsent@example.com'})

    assert refused.status_code == 400
    assert 'consent' in refused.get_json()['error']
    assert client.get('/api/check_demographics').get_json()['submitted'] is False


def test_the_tick_is_the_intake_not_the_text(tmp_path, monkeypatch):
    client = _study(tmp_path, monkeypatch, 'I agree to my answers being used in this study.')

    posted = client.post('/api/submit_demographics',
                         json={'email': 'ticked@example.com',
                               'consent': 'I agree to my answers being used in this study.'})

    assert posted.status_code == 200, posted.get_json()


def test_a_study_that_never_asked_for_consent_does_not_require_it(tmp_path, monkeypatch):
    client = _study(tmp_path, monkeypatch, '')

    assert client.post('/api/submit_demographics',
                       json={'email': 'noask@example.com'}).status_code == 200


def test_consent_is_a_column_in_the_export(app, client):
    """The shipped study sets consent_text; its CSV has to carry the tick, not just the page."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'consent-export'
    assert client.post('/api/submit_demographics', json=complete_intake()).status_code == 200
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    header = client.get('/api/admin/export').get_data(as_text=True).split('\n')[0]

    assert 'consent' in header.split(','), 'the researcher cannot show that anyone consented'
    assert 'yes' in client.get('/api/admin/export').get_data(as_text=True).split('\n')[1]


def test_the_roster_shows_the_tick(app, client):
    with client.session_transaction() as sess:
        sess['session_id'] = 'consent-roster'
    client.post('/api/submit_demographics', json=complete_intake(consent='agreed'))
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    rows = client.get('/api/admin/participants').get_json()['rows']

    assert [row for row in rows if row.get('session_id') == 'consent-roster'][0]['consent'] == 'agreed'
