"""F3 (fourth audit): one non-numeric answer shape must not break the dashboard statistics.

The submit route checks that a response names questions the study asks, and nothing about the value
inside. /api/admin/stats sums the confidence values, so one string in that list raises on every poll
from then on, and the dashboard swallows it into the console: the stat cards freeze at stale numbers.
"""
import json
import uuid

from tests.conftest import insert_demographics


def _participant(client, email, pair_id, responses):
    """A session that served trial `pair_id` and posted `responses` for it, as the browser does."""
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

    return client.post('/api/submit_survey',
                       json={'image_pair_id': pair_id, 'responses': responses, 'time_spent': 9.0})


def _stats(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client.get('/api/admin/stats')


def test_a_string_confidence_is_accepted_by_submit(client):
    """Today this is accepted, and that acceptance is what poisons the aggregate."""
    response = _participant(client, 'junk@example.com', 1,
                            {'image_quality': {'choice': 'A', 'confidence': 'very sure'}})
    assert response.status_code == 200, response.get_json()


def test_a_string_confidence_does_not_break_the_statistics(client):
    """Pre-fix this is a 500 TypeError on every poll, forever: int + str."""
    _participant(client, 'junk@example.com', 1,
                 {'image_quality': {'choice': 'A', 'confidence': 'very sure'}})

    response = _stats(client)
    assert response.status_code == 200, response.get_data(as_text=True)[:200]


def test_the_numeric_answers_are_still_averaged_and_the_junk_dropped(client):
    """The guard excludes the junk, it does not blank the real number."""
    _participant(client, 'real@example.com', 1,
                 {'image_quality': {'choice': 'A', 'confidence': 4}})
    _participant(client, 'junk@example.com', 1,
                 {'image_quality': {'choice': 'B', 'confidence': 'very sure'}})

    stats = json.loads(_stats(client).data)
    assert stats['avg_confidence'] == 4.0, stats
    assert stats['responses'] == 2, stats
