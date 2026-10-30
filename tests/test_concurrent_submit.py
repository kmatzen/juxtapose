"""Audit F3+F8: participants who submit at the same time must not lose their answers.

Every request opens its own SQLite connection, reads, then writes. Two of those upgrading from read
to write at once is the classic SQLITE_BUSY: the loser has to wait for the writer. On fast local
storage the wait is short and invisible; on a NAS-backed volume the lock outlasts the connection's
patience, the request 500s, and that is a paying participant's trial, gone, behind a client-side
error they cannot do anything about.

The test makes the contended case deterministic by patching sqlite3.connect to refuse to wait
(timeout=0) - the stand-in for a deployment where the write lock is held longer than the app is
willing to sit. The fix, PRAGMA busy_timeout, is precisely the mechanism that makes a connection
wait; journal_mode=WAL is what lets readers and the one writer share the file at all.
"""
import json
import sqlite3
import threading
import uuid

PARTICIPANTS = 16
TRIALS_EACH = 3


def _seed_participants(app_module, count):
    """Participant + demographics rows, the way /referral and /api/submit_demographics leave them."""
    db = app_module.get_db()
    rows = []
    try:
        for _ in range(count):
            session_id = f'concurrent-{uuid.uuid4()}'
            email = f'{uuid.uuid4()}@example.com'
            db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                       (session_id,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                       (participant_id, email, json.dumps({})))
            rows.append((session_id, email))
        db.commit()
    finally:
        db.close()
    return rows


def _refuse_to_wait(monkeypatch):
    """The contended-storage stand-in: a connection that will not sit and wait for the writer."""
    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        kwargs['timeout'] = 0
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, 'connect', connect)


def test_parallel_submits_all_land(app, monkeypatch):
    from src.survey import app as app_module

    pair_ids = app_module.IMAGE_PAIRS.ids[:TRIALS_EACH]
    assert len(pair_ids) == TRIALS_EACH, 'the study fixture is too small to exercise concurrency'
    sessions = [sid for sid, _ in _seed_participants(app_module, PARTICIPANTS)]
    _refuse_to_wait(monkeypatch)

    outcomes = []
    lock = threading.Lock()

    def submit(session_id, pair_id):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['session_id'] = session_id
            sess['user_pairs_count'] = TRIALS_EACH
            sess['pair_randomized'] = {}
        try:
            response = client.post('/api/submit_survey', json={
                'image_pair_id': pair_id,
                'responses': {'choice': 'a', 'confidence': 4},
                'time_spent': 3.5,
            })
            outcome = (session_id, pair_id, response.status_code)
        except Exception as exc:  # a locked connection raises out of the handler in some paths
            outcome = (session_id, pair_id, f'{type(exc).__name__}: {exc}')
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=submit, args=(sid, pair_id))
               for sid in sessions for pair_id in pair_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    failed = [o for o in outcomes if o[2] != 200]
    assert not failed, f'{len(failed)} of {len(outcomes)} parallel submits lost: {failed[:3]}'

    db = app_module.get_db()
    try:
        stored = db.execute('SELECT COUNT(*) AS n FROM survey_responses').fetchone()['n']
    finally:
        db.close()
    assert stored == PARTICIPANTS * TRIALS_EACH, f'{stored} rows stored, expected {PARTICIPANTS * TRIALS_EACH}'


def test_connections_wal_and_wait(app):
    """The two settings the concurrency fix rests on, read back off a real connection."""
    from src.survey import app as app_module

    db = app_module.get_db()
    try:
        assert db.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'
        assert int(db.execute('PRAGMA busy_timeout').fetchone()[0]) >= 5000
    finally:
        db.close()
