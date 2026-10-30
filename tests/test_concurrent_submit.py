"""Audit F3+F8: participants who submit at the same time must not lose their answers.

Every request opens its own SQLite connection, reads, then writes; on a contended volume that
read-to-write upgrade is where a submit died behind a client-side error the participant could do
nothing about. WAL and PRAGMA busy_timeout (see get_db) are what let the writers share the file,
so this test drives every submit of 16 participants through one barrier - all 48 requests reach
the write at the same moment on every run - and requires every one of them to land.

The barrier is also what exposed the flake recorded in docs/audit-findings.md (4 of 20 runs): this
test used to patch sqlite3.connect to timeout=0, and a simultaneous writer then gets SQLITE_BUSY
on the read-to-write upgrade, which busy_timeout does not cover. Patching away the mechanism the
test is about cannot end in "all submits land"; storage that will not wait at all is a deployment
condition, not a property the app can promise.
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


def _race(submit, members):
    """Every thread leaves the barrier together, so the write contention is real on every run
    instead of depending on how fast the interpreter happens to start threads."""
    start = threading.Barrier(len(members))

    def at_the_barrier(member):
        start.wait()
        submit(*member)

    threads = [threading.Thread(target=at_the_barrier, args=(member,)) for member in members]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_parallel_submits_all_land(app):
    from src.survey import app as app_module

    pair_ids = app_module.IMAGE_PAIRS.ids[:TRIALS_EACH]
    assert len(pair_ids) == TRIALS_EACH, 'the study fixture is too small to exercise concurrency'
    sessions = [sid for sid, _ in _seed_participants(app_module, PARTICIPANTS)]

    outcomes = []
    lock = threading.Lock()

    def submit(session_id, pair_id):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['session_id'] = session_id
            sess['user_pairs_count'] = TRIALS_EACH
            sess['user_image_pairs'] = list(pair_ids)
            sess['pair_randomized'] = {}
        try:
            response = client.post('/api/submit_survey', json={
                'image_pair_id': pair_id,
                'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
                'time_spent': 3.5,
            })
            outcome = (session_id, pair_id, response.status_code)
        except Exception as exc:  # a locked connection raises out of the handler in some paths
            outcome = (session_id, pair_id, f'{type(exc).__name__}: {exc}')
        with lock:
            outcomes.append(outcome)

    _race(submit, [(sid, pair_id) for sid in sessions for pair_id in pair_ids])

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
