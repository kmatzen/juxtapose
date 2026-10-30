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

    poll_stats = len(client.get('/api/admin/stats').data)
    poll_slice = len(client.get('/api/admin/results?limit=200').data)
    whole = len(client.get('/api/admin/results?limit=1000').data)

    # Split per component: the joint ratio weighed 200 rows + stats against exactly 200 rows' average, a 0.25% margin CI flipped.
    assert poll_slice <= whole / 4, 'the results slice must stay the bounded part of the poll'
    assert poll_stats * 10 < whole, 'the aggregate must not grow with the rows it summarises'


def _seed_timestamped(client, count):
    """Answers with distinct timestamps, the way a live study leaves them: one per second."""
    from src.survey import app as app_module
    from src.survey.app import get_db

    app_module.init_db()
    db = get_db()
    try:
        db.execute('INSERT INTO participants (session_id) VALUES (?)', ('paging-author',))
        pid = db.execute("SELECT id FROM participants WHERE session_id = 'paging-author'").fetchone()['id']
        for n in range(count):
            db.execute(
                'INSERT INTO survey_responses (participant_id, image_pair_id, stimulus_data, responses,'
                " time_spent, created_at) VALUES (?,?,?,?,?, datetime('2026-01-01', '+' || ? || ' seconds'))",
                (pid, n, json.dumps({'methods': {'a': 'A', 'b': 'B'}}),
                 json.dumps({'image_quality': {'choice': 'A', 'confidence': 4}}), 10.0, n))
        db.commit()
    finally:
        db.close()


def _answer_at(client, pair_id, when):
    from src.survey.app import get_db

    db = get_db()
    try:
        pid = db.execute("SELECT id FROM participants WHERE session_id = 'paging-author'").fetchone()['id']
        db.execute(
            'INSERT INTO survey_responses (participant_id, image_pair_id, stimulus_data, responses,'
            ' time_spent, created_at) VALUES (?,?,?,?,?,?)',
            (pid, pair_id, json.dumps({'methods': {'a': 'A', 'b': 'B'}}),
             json.dumps({'image_quality': {'choice': 'B', 'confidence': 4}}), 10.0, when))
        db.commit()
    finally:
        db.close()


def test_an_answer_arriving_mid_paging_never_repeats_another(client):
    """created_at is second-granularity and the page window moves with it: while the analyst paged,
    one new answer pushed the newest row of page 1 onto page 2, and appeared on no page at all."""
    as_admin(client)
    _seed_timestamped(client, count=250)

    def key(row):
        return (row['session_id'], row['image_pair_id'])

    seen = []
    for offset in (0, 100):
        page = json.loads(client.get(f'/api/admin/results?limit=100&offset={offset}').data)
        seen += [key(row) for row in page['rows']]
        if offset == 0:
            _answer_at(client, pair_id=999, when='2026-02-01 00:00:00')
    page = json.loads(client.get('/api/admin/results?limit=100&offset=200').data)
    seen += [key(row) for row in page['rows']]

    repeated = [row for row in set(seen) if seen.count(row) > 1]
    assert len(seen) == 251, f'paging showed {len(seen)} of 251 answers'
    assert not repeated, f'{len(repeated)} answer(s) shown on more than one page: {repeated[:3]}'
