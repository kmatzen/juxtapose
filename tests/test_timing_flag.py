"""Audit F5: the browser reports how long a trial took, and that number must not silently decide
the study's timing results.

Decided with the study owner: keep the raw reported value - the audit trail is what the client said,
and a stored 4.2 that used to be 0.02 is unrecoverable - and record timing_flag = 1 on rows under the
1.0s floor, below which a participant cannot have viewed three tiles and set two scales. Analysis
excludes flagged rows; nothing is overwritten.
"""
import sqlite3

from src.survey import app as app_module

OLD_SCHEMA = '''
CREATE TABLE survey_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id INTEGER NOT NULL,
    image_pair_id INTEGER,
    stimulus_data TEXT,
    responses TEXT,
    was_randomized INTEGER DEFAULT 0,
    time_spent REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
'''


def _participant(session_id, pair_id, time_spent, client):
    db = app_module.get_db()
    try:
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                   (session_id,))
        db.commit()
    finally:
        db.close()
    payload = {'image_pair_id': pair_id, 'responses': {'q1': {'choice': 'A', 'confidence': 4}}}
    if time_spent is not None:
        payload['time_spent'] = time_spent
    with client.session_transaction() as sess:
        sess['session_id'] = session_id
    response = client.post('/api/submit_survey', json=payload)
    assert response.status_code == 200, response.get_data(as_text=True)


def _row(session_id):
    db = app_module.get_db()
    try:
        return db.execute(
            'SELECT sr.* FROM survey_responses sr JOIN participants p ON p.id = sr.participant_id '
            'WHERE p.session_id = ?', (session_id,)).fetchone()
    finally:
        db.close()


def test_a_sub_floor_time_is_flagged_and_the_raw_value_survives(app, client):
    pair_id = app_module.IMAGE_PAIRS[0]['id']
    _participant('fast-002', pair_id, 0.02, client)
    row = _row('fast-002')
    assert row['time_spent'] == 0.02, 'the reported value must stay as reported'
    assert row['timing_flag'] == 1


def test_a_normal_time_is_untouched_and_unflagged(app, client):
    pair_id = app_module.IMAGE_PAIRS[0]['id']
    _participant('normal-42', pair_id, 4.2, client)
    row = _row('normal-42')
    assert row['time_spent'] == 4.2
    assert row['timing_flag'] == 0


def test_a_missing_time_is_not_flagged_as_fast(app, client):
    pair_id = app_module.IMAGE_PAIRS[0]['id']
    _participant('no-time', pair_id, None, client)
    row = _row('no-time')
    assert row['time_spent'] is None
    assert row['timing_flag'] == 0


def test_the_export_carries_the_flag(app, client):
    pair_id = app_module.IMAGE_PAIRS[0]['id']
    _participant('export-fast', pair_id, 0.3, client)
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    response = client.get('/api/admin/export')
    assert response.status_code == 200
    header, *rows = response.get_data(as_text=True).splitlines()
    assert 'timing_flag' in header.split(',')
    assert any('export-fast' in line for line in rows)


def test_an_existing_database_gains_the_column_and_keeps_its_rows(app, tmp_path, monkeypatch):
    legacy = tmp_path / 'legacy.db'
    conn = sqlite3.connect(legacy)
    conn.execute(OLD_SCHEMA)
    conn.execute('INSERT INTO survey_responses (participant_id, image_pair_id, time_spent) VALUES (1, 7, 0.05)')
    conn.commit()
    conn.close()

    monkeypatch.setattr(app_module, 'DATABASE', str(legacy))
    app_module.init_db()

    conn = sqlite3.connect(legacy)
    conn.row_factory = sqlite3.Row
    try:
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(survey_responses)')}
        rows = conn.execute('SELECT time_spent, timing_flag FROM survey_responses').fetchall()
    finally:
        conn.close()
    assert 'timing_flag' in columns
    assert len(rows) == 1, 'the additive migration must not touch stored rows'
    assert rows[0]['time_spent'] == 0.05
