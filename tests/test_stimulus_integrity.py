"""Audit #4: stimulus identity and A/B order are decided by the server, not the browser."""
import json
import uuid

from src.survey.app import get_db


def make_participant(client, email=None):
    session = f'stim-{uuid.uuid4()}'
    db = get_db()
    try:
        cursor = db.execute('INSERT INTO participants (session_id) VALUES (?)', (session,))
        db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                   (cursor.lastrowid, email or f'{session}@example.com', '{}'))
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session
    return session


def served_pair(client, index=0):
    response = client.get(f'/api/get_image_pair/{index}')
    assert response.status_code == 200
    return response.get_json()


def stored_row(session):
    db = get_db()
    try:
        row = db.execute('''
            SELECT s.stimulus_data, s.was_randomized, s.time_spent FROM survey_responses s
            JOIN participants p ON p.id = s.participant_id
            WHERE p.session_id = ?
        ''', (session,)).fetchone()
    finally:
        db.close()
    return row


def test_client_supplied_methods_are_ignored(client, app):
    """Posting swapped method names cannot move the recorded attribution."""
    from src.survey import app as app_module

    session = make_participant(client)
    pair = served_pair(client)

    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'method_a': pair['method_b'],
        'method_b': pair['method_a'],
        'stimulus_data': {'methods': {'a': pair['method_b'], 'b': pair['method_a']}},
        'was_randomized': not pair['was_randomized'],
        'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
    }, content_type='application/json')
    assert response.status_code == 200

    with client.session_transaction() as sess:
        server_said_randomized = sess['pair_randomized'][str(pair['id'])]

    row = stored_row(session)
    stim = json.loads(row['stimulus_data'])
    trial = app_module.IMAGE_PAIRS.get(pair['id'])
    a, b = (trial['method_a'], trial['method_b'])

    expected = {'a': b, 'b': a} if server_said_randomized else {'a': a, 'b': b}
    assert stim['methods'] == expected
    assert row['was_randomized'] == (1 if server_said_randomized else 0)


def test_admin_preferred_method_follows_the_served_pair(client):
    """The dashboard stat is derived from what the server showed as A."""
    session = make_participant(client)
    pair = served_pair(client)

    client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'responses': {'image_quality': {'choice': 'A', 'confidence': 5}},
    }, content_type='application/json')

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    rows = client.get('/api/admin/results').get_json()['rows']
    mine = [r for r in rows if r['image_pair_id'] == pair['id']]
    assert len(mine) == 1
    assert mine[0]['image_quality_preferred_method'] == pair['method_a']


def test_stored_stimulus_carries_the_trial_content(client, app):
    """The stored row describes the real trial, not a browser-supplied copy."""
    from src.survey import app as app_module

    session = make_participant(client)
    pair = served_pair(client)

    client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'prompt': 'prompt invented by the browser',
        'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
    }, content_type='application/json')

    stim = json.loads(stored_row(session)['stimulus_data'])
    trial = app_module.IMAGE_PAIRS.get(pair['id'])
    assert stim['inputs']['prompt'] == trial['prompt']
    assert stim['prompt'] == trial['prompt']
    assert stim['trial_id'] == trial['id']


def test_the_ignored_payload_keys_change_nothing(client, app):
    """Audit #18: the frontend stopped sending stimulus_data and was_randomized, and the stored row is identical with and without them."""
    from src.survey import app as app_module

    session = make_participant(client)
    pair = served_pair(client)
    answers = {'image_quality': {'choice': 'A', 'confidence': 4}}

    def post(extra):
        body = {'image_pair_id': pair['id'], 'responses': answers, 'time_spent': 9.5}
        body.update(extra)
        response = client.post('/api/submit_survey', json=body, content_type='application/json')
        assert response.status_code == 200
        row = stored_row(session)
        return json.loads(row['stimulus_data']), row['was_randomized'], row['time_spent']

    thin = post({})
    fat = post({
        'stimulus_data': {'prompt': 'invented', 'method_a': 'x', 'method_b': 'y', 'identity_urls': []},
        'was_randomized': not pair['was_randomized'],
    })

    assert thin == fat
    assert thin[0]['prompt'] == app_module.IMAGE_PAIRS.get(pair['id'])['prompt']


def test_submit_for_unknown_trial_is_rejected(client):
    session = make_participant(client)

    response = client.post('/api/submit_survey', json={
        'image_pair_id': 999999,
        'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
    }, content_type='application/json')

    assert response.status_code == 404
    assert 'error' in response.get_json()


def test_randomization_recorded_per_trial(client):
    """Each served trial records its own order."""
    session = make_participant(client)
    first = served_pair(client, 0)
    second = served_pair(client, 1)

    with client.session_transaction() as sess:
        recorded = dict(sess['pair_randomized'])

    assert str(first['id']) in recorded
    assert str(second['id']) in recorded
