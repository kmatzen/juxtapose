"""Seeded randomness: a seeded run must reproduce it, production must keep randomising it."""
import json
import random
import uuid

from src.survey import app as app_module


def _flip(key, session_id='participant-1'):
    with app_module.app.test_request_context():
        app_module.session['session_id'] = session_id
        return app_module._randomize_pair(key)


def test_the_seeded_flip_survives_extra_draws(monkeypatch):
    monkeypatch.setenv('E2E_RANDOM_SEED', '20260301')
    first = _flip(7)
    for _ in range(5):
        random.random()
    assert _flip(7) == first


def test_the_seeded_flip_does_not_follow_the_session_id(monkeypatch):
    """A shot server's session id is a fresh uuid4 every run, so keying on it makes every run differ."""
    monkeypatch.setenv('E2E_RANDOM_SEED', '20260301')
    assert len({_flip(7, str(uuid.uuid4())) for _ in range(12)}) == 1


def test_the_seeded_flip_still_varies_across_pairs(monkeypatch):
    monkeypatch.setenv('E2E_RANDOM_SEED', '20260301')
    assert len({_flip(pair) for pair in range(20)}) == 2


def test_an_unseeded_flip_consumes_the_stream(monkeypatch):
    monkeypatch.delenv('E2E_RANDOM_SEED', raising=False)
    assert len({_flip(1) for _ in range(20)}) == 2


PAIR_IDS = list(range(10))


def _served(client, index=0):
    response = client.get(f'/api/get_image_pair/{index}')
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    return response.get_json()


def _joined_client(app, email):
    client = app.test_client()
    session_id = f'flip-{uuid.uuid4()}'
    with client.session_transaction() as sess:
        sess['session_id'] = session_id
    response = client.post('/api/submit_demographics',
                           json={'email': email, 'occupation': 'engineer'},
                           content_type='application/json')
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    return client, session_id


def test_a_repeat_request_for_a_trial_keeps_the_position_it_was_served_in(client):
    """F8 (fifth audit): every pair request drew a fresh coin, so a mid-trial refresh - what the
    app's own banner tells the participant to do - swapped the tiles, 19 times in 40 sessions.
    """
    changed = 0
    for _ in range(20):
        with client.session_transaction() as sess:
            sess['session_id'] = f'flip-{uuid.uuid4()}'
        first = _served(client)['was_randomized']
        changed += sum(1 for _ in range(5) if _served(client)['was_randomized'] != first)
    assert changed == 0, (
        f'the same trial changed A/B position on {changed} of 100 repeat requests for 20 sessions')


def test_the_stored_row_keeps_the_order_the_participant_was_first_served(client):
    client, session_id = _joined_client(client.application, 'first-draw@example.com')
    first = _served(client)
    client.post('/api/submit_survey',
                json={'image_pair_id': first['id'],
                      'responses': {q['name']: {'choice': 'A', 'confidence': 4}
                                    for q in app_module.CONFIG['questions']
                                    if (q.get('required') or q['type'] == 'ab_preference')
                                    and not q.get('depends_on')}},
                content_type='application/json')
    with client.application.app_context():
        row = app_module.get_db().execute(
            'SELECT s.was_randomized, s.stimulus_data FROM survey_responses s '
            'JOIN participants p ON p.id = s.participant_id WHERE p.session_id = ?',
            (session_id,)).fetchone()
    stored = json.loads(row['stimulus_data'])
    assert (row['was_randomized'], stored['methods']) == (int(first['was_randomized']),
                                                          first['methods']), (
        'the stored order is not the order this session was served')


def _assign(session_id, seed='20260301'):
    import os
    if seed is None:
        os.environ.pop('E2E_RANDOM_SEED', None)
    else:
        os.environ['E2E_RANDOM_SEED'] = seed
    with app_module.app.test_request_context():
        app_module.session['session_id'] = session_id
        return tuple(app_module._assign_pairs(PAIR_IDS, 5))


def test_the_seeded_assignment_is_unmoved_by_stream_draws(monkeypatch):
    monkeypatch.setenv('E2E_RANDOM_SEED', '20260301')
    first = _assign('participant-1')
    for _ in range(7):
        random.random()
    assert _assign('participant-1') == first


def test_the_seeded_assignment_varies_across_participants(monkeypatch):
    """Per-participant variety is the counterbalancing; a seeded run must not flatten it."""
    monkeypatch.setenv('E2E_RANDOM_SEED', '20260301')
    assert len({_assign(f'participant-{n}') for n in range(12)}) > 1


def test_an_unseeded_assignment_consumes_the_stream(monkeypatch):
    monkeypatch.delenv('E2E_RANDOM_SEED', raising=False)
    assert len({_assign('participant-1', seed=None) for _ in range(10)}) > 1
