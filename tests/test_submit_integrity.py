"""Audit #4, #6, #9: one trial stores one answer, from the trials this participant was served.

The write was a check-then-insert with nothing underneath it, the request body had no size limit and
no shape, and any pair id in the study was submittable.
"""
import sqlite3
import uuid

import pytest

from src.survey.app import get_db

ANSWER = {'image_quality': {'choice': 'A', 'confidence': 3}}


def _participant(client, tag):
    session_id = f'integrity-{tag}-{uuid.uuid4()}'
    db = get_db()
    try:
        cursor = db.execute('INSERT INTO participants (session_id) VALUES (?)', (session_id,))
        db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                   (cursor.lastrowid, f'{session_id}@example.com', '{}'))
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session_id
    return session_id


def _stored_pair_ids(session_id):
    db = get_db()
    try:
        rows = db.execute('''
            SELECT s.image_pair_id FROM survey_responses s
            JOIN participants p ON p.id = s.participant_id
            WHERE p.session_id = ?
        ''', (session_id,)).fetchall()
    finally:
        db.close()
    return [row['image_pair_id'] for row in rows]


def test_one_row_per_participant_and_trial(app, client):
    """The invariant the check-then-insert was standing in for, now enforced by the schema: on the
    audit's deployment 4 parallel submits of one trial left 4 answers for one trial."""
    session_id = _participant(client, 'unique')
    pair = client.get('/api/get_image_pair/0').get_json()
    pair_id = pair['id']
    assert client.post('/api/submit_survey', json={
        'image_pair_id': pair_id, 'responses': ANSWER, 'time_spent': 5.0}).status_code == 200

    db = get_db()
    try:
        participant_id = db.execute('SELECT id FROM participants WHERE session_id = ?',
                                    (session_id,)).fetchone()['id']
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('''
                INSERT INTO survey_responses
                (participant_id, image_pair_id, responses, time_spent) VALUES (?, ?, ?, ?)
            ''', (participant_id, pair_id, '{}', 5.0))
    finally:
        db.close()

    assert _stored_pair_ids(session_id) == [pair_id]


def test_a_resubmit_updates_the_answer_of_the_trial(app, client):
    _participant(client, 'resubmit')
    pair = client.get('/api/get_image_pair/0').get_json()

    client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'], 'responses': ANSWER, 'time_spent': 5.0})
    second = {'image_quality': {'choice': 'B', 'confidence': 5}}
    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'], 'responses': second, 'time_spent': 8.0})

    assert response.status_code == 200
    db = get_db()
    try:
        rows = db.execute('SELECT responses, time_spent FROM survey_responses').fetchall()
    finally:
        db.close()
    assert len(rows) == 1, 'the trial the participant re-answered has one row'
    assert '"choice": "B"' in rows[0]['responses']
    assert rows[0]['time_spent'] == 8.0


def test_an_oversized_answer_body_is_refused(app, client):
    """The browser sends a few hundred bytes; a 2 MB blob is not an answer and must not be stored."""
    session_id = _participant(client, 'cap')
    pair = client.get('/api/get_image_pair/0').get_json()
    huge = dict(ANSWER, notes='x' * (2 * 1024 * 1024))

    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'], 'responses': huge, 'time_spent': 5.0})

    assert response.status_code == 413, f'a 2 MB answer came back {response.status_code}'
    assert _stored_pair_ids(session_id) == []


def test_answers_must_belong_to_the_study(app, client):
    session_id = _participant(client, 'keys')
    pair = client.get('/api/get_image_pair/0').get_json()

    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'responses': {'what_is_this_question': {'choice': 'A', 'confidence': 1}},
        'time_spent': 5.0})

    assert response.status_code == 400, 'answers the study never asked cannot be stored'
    assert _stored_pair_ids(session_id) == []


def test_a_pair_the_participant_was_never_served_is_refused(app, client):
    """Answers are the study's data: any in-study id used to be submittable by POST."""
    from src.survey import app as app_module
    session_id = _participant(client, 'assign')
    assigned = app_module.IMAGE_PAIRS.ids[:-1]
    unassigned = app_module.IMAGE_PAIRS.ids[-1]
    assert unassigned not in assigned, 'the study fixture needs two pairs to test assignment'
    with client.session_transaction() as sess:
        sess['user_image_pairs'] = assigned
        sess['user_pairs_count'] = len(assigned)

    response = client.post('/api/submit_survey', json={
        'image_pair_id': unassigned, 'responses': ANSWER, 'time_spent': 5.0})

    assert response.status_code == 400, f'unassigned pair {unassigned} came back {response.status_code}'
    assert _stored_pair_ids(session_id) == []
