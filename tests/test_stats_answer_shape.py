"""F3 (fourth audit) + F7 (sixth): one non-numeric answer shape must not break the dashboard.

The submit route now refuses an answer the page could not have posted (F7), and the statistics still
survive the rows stored before that boundary existed: /api/admin/stats sums the confidence values,
so one string in that list raised on every poll from then on, and the dashboard swallows it into the
console: the stat cards freeze at stale numbers.
"""
import json
import uuid

from tests.conftest import insert_demographics


def _participant_row(client, email, pair_id):
    """A session that served trial `pair_id`, the way the browser does. Returns its participant row."""
    from src.survey.app import get_db

    session_id = f'stats-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute('INSERT INTO participants (session_id, browser, os) VALUES (?, ?, ?)',
                   (session_id, 'script', 'curl'))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, email)
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = session_id
        sess['user_image_pairs'] = [pair_id]

    return participant_id


def _participant(client, email, pair_id, responses):
    """Post `responses` for trial `pair_id` from a fresh session, the way the browser does."""
    _participant_row(client, email, pair_id)
    return client.post('/api/submit_survey',
                       json={'image_pair_id': pair_id, 'responses': responses, 'time_spent': 9.0})


def _stored_row(client, email, pair_id, responses):
    """A row written straight to the database: answers the boundary did not screen yet."""
    from tests.conftest import insert_response
    from src.survey.app import get_db

    participant_id = _participant_row(client, email, pair_id)
    with client.application.app_context():
        db = get_db()
        insert_response(db, participant_id, pair_id, responses)
        db.commit()
        db.close()


def _stats(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client.get('/api/admin/stats')


def test_a_string_confidence_is_rejected_by_submit(client):
    """F7 (sixth audit): the acceptance was what poisoned the aggregate, so the boundary refuses it."""
    response = _participant(client, 'junk@example.com', 1,
                            {'image_quality': {'choice': 'A', 'confidence': 'very sure'}})
    assert response.status_code == 400, response.get_json()


def test_a_stored_string_confidence_does_not_break_the_statistics(client):
    """Pre-fix this is a 500 TypeError on every poll, forever: int + str. Rows stored before the
    boundary existed still have to be survived."""
    _stored_row(client, 'junk@example.com', 1,
                {'image_quality': {'choice': 'A', 'confidence': 'very sure'}})

    response = _stats(client)
    assert response.status_code == 200, response.get_data(as_text=True)[:200]


def test_the_numeric_answers_are_still_averaged_and_the_junk_dropped(client):
    """The guard excludes the junk, it does not blank the real number."""
    _participant(client, 'real@example.com', 1,
                 {'image_quality': {'choice': 'A', 'confidence': 4}})
    _stored_row(client, 'junk@example.com', 1,
                {'image_quality': {'choice': 'B', 'confidence': 'very sure'}})

    stats = json.loads(_stats(client).data)
    assert stats['avg_confidence'] == 4.0, stats
    assert stats['responses'] == 2, stats
