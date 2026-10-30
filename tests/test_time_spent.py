"""Audit #19: time_spent arrives from the browser and must not land in the DB untyped."""
import uuid

from src.survey.app import get_db


def make_participant(client):
    session = f'ts-{uuid.uuid4()}'
    db = get_db()
    try:
        db.execute('INSERT INTO participants (session_id) VALUES (?)', (session,))
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session
    return session


def submit(client, time_spent, index=0):
    pair = client.get(f'/api/get_image_pair/{index}').get_json()
    payload = {
        'image_pair_id': pair['id'],
        'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
    }
    if time_spent is not _OMITTED:
        payload['time_spent'] = time_spent
    return client.post('/api/submit_survey', json=payload, content_type='application/json')


class _OMITTED:
    pass


def stored_time_spent(session):
    db = get_db()
    try:
        row = db.execute('''
            SELECT s.time_spent FROM survey_responses s
            JOIN participants p ON p.id = s.participant_id
            WHERE p.session_id = ?
        ''', (session,)).fetchone()
    finally:
        db.close()
    return row['time_spent'] if row else None


def test_numeric_string_is_stored_as_a_number(client):
    session = make_participant(client)
    assert submit(client, '4.2').status_code == 200
    value = stored_time_spent(session)
    assert isinstance(value, float)
    assert value == 4.2


def test_non_numeric_time_spent_is_stored_as_null(client):
    """A junk value must not enter a REAL column that the dashboard averages."""
    session = make_participant(client)
    assert submit(client, 'a minute').status_code == 200
    assert stored_time_spent(session) is None


def test_absent_time_spent_is_stored_as_null(client):
    session = make_participant(client)
    assert submit(client, _OMITTED).status_code == 200
    assert stored_time_spent(session) is None


def test_dashboard_average_ignores_garbage(client):
    """SQLite coerces a text time to 0, so garbage used to be averaged in as zero seconds."""
    session = make_participant(client)
    submit(client, 'soon')
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    stats = client.get('/api/admin/stats').get_json()

    assert stats['avg_time'] is None


def test_dashboard_average_excludes_flagged_timings(client):
    """A timing flagged as not a judgement must not move the card the study owner reads."""
    session = make_participant(client)
    submit(client, 12.0)
    submit(client, 0.02, index=1)
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    stats = client.get('/api/admin/stats').get_json()

    assert stats['avg_time'] == 12.0


def test_dashboard_average_excludes_flagged_timings_at_both_ends(client):
    """The card drops sub-floor rows and over-ceiling rows, and keeps the judgements."""
    session = make_participant(client)
    submit(client, 12.0)
    submit(client, 0.02, index=1)
    submit(client, 900.0, index=2)
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    assert client.get('/api/admin/stats').get_json()['avg_time'] == 12.0
