"""Audit #2: a retake must not destroy finished work before it is confirmed."""
import hashlib
import json
import uuid

import pytest

from src.survey.app import get_db
from tests.conftest import insert_demographics, insert_response

EMAIL = 'retaker@example.com'


def _log_entries(log_file):
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text().splitlines()]


def seed_completed_participant(email=EMAIL, responses=3):
    """A previous participant with finished responses, as a retake target."""
    session = f'seeded-{uuid.uuid4()}'
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
            (session,))
        pid = cursor.lastrowid
        insert_demographics(db, pid, email, occupation='Researcher')
        for pair in range(responses):
            insert_response(db, pid, pair,
                            {'image_quality': {'choice': 'A', 'confidence': 4}})
        db.commit()
    finally:
        db.close()
    return session


def response_count_for_email(email=EMAIL):
    db = get_db()
    try:
        return db.execute('''
            SELECT COUNT(*) FROM survey_responses s
            JOIN demographics d ON d.participant_id = s.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchone()[0]
    finally:
        db.close()


def demographics_count_for_email(email=EMAIL):
    db = get_db()
    try:
        return db.execute('SELECT COUNT(*) FROM demographics WHERE email = ?',
                          (email,)).fetchone()[0]
    finally:
        db.close()


def submit(client, session, email=EMAIL, **extra):
    with client.session_transaction() as sess:
        sess['session_id'] = session
    return client.post('/api/submit_demographics',
                       json={'email': email, **extra},
                       content_type='application/json')


def test_first_submit_reports_retaking_without_deleting(client):
    """The prompt comes first: is_retaking is reported, data is untouched."""
    seed_completed_participant(responses=5)

    response = submit(client, 'retake-first-submit')

    assert response.status_code == 200
    assert response.get_json()['is_retaking'] is True
    assert response_count_for_email() == 5
    # The seeded row plus this session's row: the existing one was not deleted.
    assert demographics_count_for_email() == 2


def test_cancel_after_prompt_leaves_every_response(client):
    """Cancel = the confirmed request is never sent, so nothing is destroyed."""
    seed_completed_participant(responses=5)

    submit(client, 'cancel-session')

    assert response_count_for_email() == 5
    assert demographics_count_for_email() == 2


def test_confirmed_retake_deletes_prior_responses(client):
    seed_completed_participant(responses=5)

    submit(client, 'retake-first-submit')
    confirmed = submit(client, 'retake-first-submit', confirm_retake=True)

    assert confirmed.status_code == 200
    assert confirmed.get_json()['success'] is True
    assert response_count_for_email() == 0


def test_confirmed_retake_is_audit_logged(client, app, tmp_path, monkeypatch):
    log_file = tmp_path / 'audit.log'
    monkeypatch.setattr('src.survey.app.AUDIT_LOG_FILE', str(log_file))
    seed_completed_participant(responses=2)

    submit(client, 'logged-retake')
    submit(client, 'logged-retake', confirm_retake=True)

    entries = _log_entries(log_file)
    retake = [e for e in entries if e['action'] == 'RETAKE_DELETE']
    assert len(retake) == 1
    # Audit F11: the log carries a stable hash, not the address, so it stays joinable and PII-free.
    assert retake[0]['details']['email'] == hashlib.sha256(EMAIL.encode()).hexdigest()[:16]
    assert EMAIL not in log_file.read_text()
    assert retake[0]['details']['responses_deleted'] == 2


def test_unconfirmed_submit_never_writes_the_audit_entry(client, app, tmp_path, monkeypatch):
    log_file = tmp_path / 'audit.log'
    monkeypatch.setattr('src.survey.app.AUDIT_LOG_FILE', str(log_file))
    seed_completed_participant(responses=2)

    submit(client, 'unlogged-retake')

    entries = _log_entries(log_file)
    assert [e for e in entries if e['action'] == 'RETAKE_DELETE'] == []


def test_new_participant_is_not_marked_retaking(client):
    response = submit(client, 'brand-new-session', email='fresh@example.com')

    assert response.status_code == 200
    assert response.get_json()['is_retaking'] is False


def test_retake_without_prior_responses_needs_no_confirmation(client):
    """A participant who only submitted demographics is not a retake."""
    seed_completed_participant(email='demographics-only@example.com', responses=0)

    response = submit(client, 'demo-only', email='demographics-only@example.com')

    assert response.status_code == 200
    assert response.get_json()['is_retaking'] is False
