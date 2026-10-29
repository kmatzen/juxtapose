"""Audit #13: the dashboard's 30s poll must not re-download the whole study."""
import json


def seed(client, participants, per_participant):
    from src.survey import app as app_module
    from src.survey.app import get_db

    app_module.init_db()
    db = get_db()
    try:
        for n in range(participants):
            sid = f'page-{n}'
            db.execute('INSERT INTO participants (session_id) VALUES (?)', (sid,))
            pid = db.execute('SELECT id FROM participants WHERE session_id = ?', (sid,)).fetchone()['id']
            db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?,?,?)',
                       (pid, f'page-{n}@example.com', '{"occupation": "researcher"}'))
            for i in range(per_participant):
                db.execute(
                    'INSERT INTO survey_responses (participant_id, image_pair_id, stimulus_data,'
                    ' responses, was_randomized, time_spent) VALUES (?,?,?,?,?,?)',
                    (pid, i,
                     json.dumps({'methods': {'a': 'Method-A', 'b': 'Method-B'}}),
                     json.dumps({'image_quality': {'choice': 'A' if i % 2 else 'B', 'confidence': 4}}),
                     1, 100 + i))
        db.commit()
    finally:
        db.close()


def as_admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


def test_results_are_paged_and_report_the_total(client):
    as_admin(client)
    seed(client, participants=3, per_participant=4)

    page = json.loads(client.get('/api/admin/results?limit=5&offset=0').data)
    assert page['total'] == 12
    assert len(page['rows']) == 5
    assert page['limit'] == 5

    rest = json.loads(client.get('/api/admin/results?limit=5&offset=5').data)
    assert len(rest['rows']) == 5
    assert [r['session_id'] for r in page['rows']] != [r['session_id'] for r in rest['rows']]


def test_page_size_is_capped(client):
    as_admin(client)
    seed(client, participants=1, per_participant=2)

    assert json.loads(client.get('/api/admin/results?limit=100000').data)['limit'] == 1000
    assert json.loads(client.get('/api/admin/results?limit=-5').data)['limit'] == 1


def test_stats_endpoint_aggregates_without_rows(client):
    as_admin(client)
    seed(client, participants=2, per_participant=10)

    stats = json.loads(client.get('/api/admin/stats').data)

    assert stats['participants'] == 2
    assert stats['responses'] == 20
    assert stats['preferences']['image_quality'] == {'Method-A': 10, 'Method-B': 10}
    assert stats['avg_confidence'] == 4.0
    assert stats['avg_time'] == 104.5
    assert 'rows' not in stats


def test_poll_payload_does_not_grow_with_the_study(client):
    as_admin(client)
    seed(client, participants=50, per_participant=20)

    poll = (len(client.get('/api/admin/stats').data)
            + len(client.get('/api/admin/results?limit=200').data))
    whole = len(client.get('/api/admin/results?limit=1000').data)

    assert poll < whole / 5
