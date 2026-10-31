"""Audit 6 F1: a confirm may only delete answers this session's own address owns.

A session is free (GET / mints one) and the CSRF token sits on the page it fetches, so a delete
that trusts the email in the request body is an unauthenticated wipe of any address in the study.
The suite that covers retake posts twice, which is why the single-post path shipped open.
"""
from tests.conftest import complete_intake
import json
import uuid

from src.survey.app import get_db
from tests.conftest import insert_demographics, insert_response

VICTIM = 'victim@lab.example'
STRANGER = 'stranger@lab.example'


def seed_participant(email, responses=3):
    """A finished participant, as a retake target."""
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO participants (session_id) VALUES (?)",
                            (f'seeded-{uuid.uuid4()}',))
        pid = cursor.lastrowid
        insert_demographics(db, pid, email, occupation='Researcher')
        for pair in range(responses):
            insert_response(db, pid, pair,
                            {'image_quality': {'choice': 'A', 'confidence': 4}})
        db.commit()
    finally:
        db.close()


def response_count(email):
    db = get_db()
    try:
        return db.execute('''
            SELECT COUNT(*) FROM survey_responses s
            JOIN demographics d ON d.participant_id = s.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchone()[0]
    finally:
        db.close()


def post(client, session_id, **payload):
    with client.session_transaction() as sess:
        sess['session_id'] = session_id
    return client.post('/api/submit_demographics', json=complete_intake(payload),
                       content_type='application/json')


def test_a_first_post_cannot_delete_another_addresss_answers(client):
    """The attack: one POST, no prior demographics, a borrowed address."""
    seed_participant(VICTIM, responses=3)

    response = post(client, 'attacker-session', email=VICTIM, confirm_retake=True)

    assert response.status_code == 403
    assert response_count(VICTIM) == 3


def test_confirm_for_an_address_the_session_does_not_own_is_refused(client):
    """Owning one address does not license deleting another."""
    seed_participant(VICTIM, responses=4)
    post(client, 'stranger-session', email=STRANGER)

    response = post(client, 'stranger-session', email=VICTIM, confirm_retake=True)

    assert response.status_code == 403
    assert response_count(VICTIM) == 4


def test_the_participants_own_retake_still_deletes(client):
    """The flow the modal drives is unchanged: prompt, then confirm, then the rows are gone."""
    seed_participant(VICTIM, responses=5)
    prompt = post(client, 'victim-session', email=VICTIM)
    assert prompt.get_json()['is_retaking'] is True

    response = post(client, 'victim-session', email=VICTIM, confirm_retake=True)

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert response_count(VICTIM) == 0


def test_a_refused_confirm_leaves_an_audit_line(client, app, tmp_path, monkeypatch):
    """A refused wipe of a study's answers is worth a line in the log."""
    log_file = tmp_path / 'audit.log'
    monkeypatch.setattr('src.survey.app.AUDIT_LOG_FILE', str(log_file))
    seed_participant(VICTIM, responses=2)

    post(client, 'attacker-session', email=VICTIM, confirm_retake=True)

    actions = [json.loads(line)['action']
               for line in log_file.read_text().splitlines()]
    assert 'RETAKE_DELETE_REFUSED' in actions
    assert 'RETAKE_DELETE' not in actions
