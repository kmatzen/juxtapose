"""Seeded randomness: a seeded run must reproduce it, production must keep randomising it."""
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
