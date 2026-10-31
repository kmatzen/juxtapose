"""JSON spells `Infinity`, and the timing column has no rule against it.

Measured on 156fe69: `{"time_spent": Infinity}` and `{"time_spent": -Infinity}` are accepted, stored
as `inf` and `-inf`, and written to the CSV as the literal `inf`. The app's own average survives
because the 120-second ceiling flags those rows, but a report written against the column - the CSV is
what the README calls the record - reads `SELECT AVG(time_spent)` as **NULL** over one +inf and one
-inf row, with MIN and MAX at the infinities. NaN already lands as NULL, so the column is only
half-guarded.
"""
import json
import sqlite3

import pytest
import yaml

from src.survey import app as app_module
from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Timing', 'pairs_per_user': 1},
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
    row = '\t'.join(['a prompt', 'A', 'B', 'https://x/a.png', 'https://x/b.png', '', ''])
    (tmp_path / 'pairs.tsv').write_text(row + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    return app.test_client()


def _answer(client, email, time_spent):
    """Post one trial answer, as a participant of their own, with `time_spent` written verbatim."""
    participant = client.application.test_client()   # one session owns one participant
    participant.get('/')
    posted = participant.post('/api/submit_demographics', json={'email': email, 'consent': 'yes'})
    assert posted.status_code == 200, posted.get_json()
    served = participant.get('/api/get_image_pair/0').get_json()
    body = '{"image_pair_id": %d, "responses": {"quality": {"choice": "A", "confidence": 4}},' \
           ' "time_spent": %s}' % (served['id'], time_spent)
    return participant.post('/api/submit_survey', data=body, content_type='application/json')


def _stored(client):
    with client.application.app_context():
        db = app_module.get_db()
        try:
            return [row['time_spent'] for row in
                    db.execute('SELECT time_spent FROM survey_responses ORDER BY id')]
        finally:
            db.close()


@pytest.mark.parametrize('spelling', ['Infinity', '-Infinity', 'NaN'])
def test_a_time_that_is_not_a_finite_number_is_stored_as_no_time(client, spelling):
    response = _answer(client, 'nonfinite@example.com', spelling)
    assert response.status_code == 200, response.get_json()
    assert _stored(client) == [None]


def test_the_column_stays_averagable(client):
    for email, spelling in [('a@e.com', 'Infinity'), ('b@e.com', '-Infinity'),
                            ('c@e.com', '12'), ('d@e.com', '32')]:
        assert _answer(client, email, spelling).status_code == 200
    with client.application.app_context():
        db = app_module.get_db()
        try:
            row = db.execute('SELECT AVG(time_spent) AS avg_time, MIN(time_spent) AS min_time,'
                             ' MAX(time_spent) AS max_time FROM survey_responses').fetchone()
        finally:
            db.close()
    assert row['avg_time'] == pytest.approx(22.0), row
    assert (row['min_time'], row['max_time']) == (12.0, 32.0), row


def test_the_export_carries_no_infinity(client):
    assert _answer(client, 'csv@example.com', 'Infinity').status_code == 200
    client.get('/')
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    lines = client.get('/api/admin/export').get_data(as_text=True).splitlines()
    column = lines[0].split(',').index('time_spent')
    cells = [line.split(',')[column] for line in lines[1:]]
    assert cells == [''], cells


def test_the_dashboard_average_ignores_a_non_finite_time(client):
    """The dashboard's own average is the number an analyst reads off the screen."""
    assert _answer(client, 'stat1@example.com', 'Infinity').status_code == 200
    assert _answer(client, 'stat2@example.com', '12').status_code == 200
    client.get('/')
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    stats = client.get('/api/admin/stats').get_json()
    assert stats['avg_time'] == pytest.approx(12.0), stats


def test_a_real_time_is_kept(client):
    assert _answer(client, 'real@example.com', '12.5').status_code == 200
    assert _stored(client) == [12.5]


def test_a_time_that_is_not_a_number_is_stored_as_no_time(client):
    """The guard next door: a string lands as NULL rather than as text in a REAL column."""
    assert _answer(client, 'text@example.com', '"a minute"').status_code == 200
    assert _stored(client) == [None]
