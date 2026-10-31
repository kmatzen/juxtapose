"""Audit #2: one retake posted demographics twice, and every answer was counted twice."""
from tests.conftest import complete_intake
import csv
import io
import sqlite3

ANSWERS = {'image_quality': {'choice': 'A', 'confidence': 3}}


def _retake_with_three_answers(client):
    """The retake flow: confirm wipes the old participant, the session posts demographics twice."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'retaking-session'
    for _ in range(2):
        response = client.post('/api/submit_demographics',
                               json=complete_intake({'email': 'twice@example.com', 'occupation': 'software-engineer'}))
        assert response.status_code == 200, response.get_json()
    for index in range(3):
        pair = client.get(f'/api/get_image_pair/{index}').get_json()
        submitted = client.post('/api/submit_survey', json={
            'image_pair_id': pair['id'], 'responses': ANSWERS, 'time_spent': 9.0})
        assert submitted.status_code == 200, submitted.get_json()


def _admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


def test_a_retaking_participant_is_counted_once(app, client):
    _retake_with_three_answers(_admin(client))

    page = client.get('/api/admin/results').get_json()

    assert page['total'] == 3
    assert len(page['rows']) == 3, 'every answer appears once, not once per demographics row'
    assert [row['email'] for row in page['rows']] == ['twice@example.com'] * 3


def test_the_csv_shows_the_rows_the_label_claims(app, client):
    _retake_with_three_answers(_admin(client))

    rows = list(csv.reader(io.StringIO(client.get('/api/admin/export').get_data(as_text=True))))

    assert len(rows) - 1 == 3, 'the "Showing N of M" label counts the same rows the table lists'


def test_new_demographics_replace_the_participant_row(app, client):
    with client.session_transaction() as sess:
        sess['session_id'] = 'editing-session'
    client.post('/api/submit_demographics', json=complete_intake({'email': 'old@example.com', 'occupation': 'other-non-tech'}))
    client.post('/api/submit_demographics', json=complete_intake({'email': 'new@example.com', 'occupation': 'software-engineer'}))

    from src.survey import app as app_module
    db = sqlite3.connect(app_module.DATABASE)
    db.row_factory = sqlite3.Row
    rows = db.execute('SELECT email, data FROM demographics').fetchall()
    db.close()

    assert len(rows) == 1, 'a participant has one demographics row, the one they last submitted'
    assert rows[0]['email'] == 'new@example.com'


def _seed_study_from_before_the_constraint(path, participants, per_participant):
    """The schema a running study was left with: no UNIQUE, and the duplicates already in it."""
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE participants ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT UNIQUE NOT NULL)')
    db.execute('CREATE TABLE demographics ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, participant_id INTEGER NOT NULL, '
               'email TEXT, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    for participant in range(participants):
        db.execute('INSERT INTO participants (session_id) VALUES (?)', (f'seed-{participant}',))
        for _ in range(per_participant):
            db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                       (participant + 1, f'seed{participant}@example.com', '{}'))
    db.commit()
    db.close()


def test_an_existing_study_is_deduped_and_stays_deduped(app, tmp_path, monkeypatch):
    from src.survey import app as app_module
    legacy = str(tmp_path / 'legacy.db')
    _seed_study_from_before_the_constraint(legacy, participants=4, per_participant=3)
    monkeypatch.setattr(app_module, 'DATABASE', legacy)
    with app.test_client() as client:
        assert client.get('/health').status_code == 200, 'init_db runs on the first request'

    db = sqlite3.connect(app_module.DATABASE)
    db.row_factory = sqlite3.Row
    duplicates = db.execute(
        'SELECT COUNT(*) AS n FROM (SELECT participant_id FROM demographics '
        'GROUP BY participant_id HAVING COUNT(*) > 1)').fetchone()['n']
    rows = db.execute('SELECT id, participant_id FROM demographics').fetchall()
    db.close()

    assert duplicates == 0, 'the join that multiplies answers needs one row to join to'
    assert {row['participant_id'] for row in rows} == {1, 2, 3, 4}
    assert len(rows) == 4, 'the newest row per participant is the one kept'

    app_module._DB_READY = False
    app_module.init_db()
    app_module.init_db()

    db = sqlite3.connect(app_module.DATABASE)
    assert db.execute('SELECT COUNT(*) FROM demographics').fetchone()[0] == 4, (
        're-running the migration must not touch a database it already fixed')
    db.close()
