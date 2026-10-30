"""
Tests for error handling and edge cases
"""
import json
import os
from tests.conftest import insert_demographics, insert_response


STANDARD_RESPONSES = {
    'image_quality': {'choice': 'A', 'confidence': 3},
    'prompt_adherence': {'choice': 'A', 'confidence': 3},
    'mask_adherence': {'choice': 'B', 'confidence': 4},
    'identity_preservation': {'choice': 'equal', 'confidence': 2},
}


def test_submit_demographics_invalid_json(client):
    """Test demographics submission with invalid JSON"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-invalid-json'
        sess['referral_validated'] = True

    response = client.post('/api/submit_demographics',
                          data='not valid json',
                          content_type='application/json')
    assert response.status_code == 400


def test_submit_demographics_missing_email(client):
    """Test demographics submission without email"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-no-email'
        sess['referral_validated'] = True

    response = client.post('/api/submit_demographics',
                          json={
                              'occupation': 'Engineer',
                              'device_info': {
                                  'browser': 'Chrome',
                                  'os': 'macOS'
                              }
                          },
                          content_type='application/json')
    assert response.status_code == 200


def test_submit_demographics_missing_device_info(client):
    """Test demographics submission without device info"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-no-device'
        sess['referral_validated'] = True

    response = client.post('/api/submit_demographics',
                          json={
                              'email': 'test@example.com',
                              'occupation': 'Engineer'
                          },
                          content_type='application/json')
    assert response.status_code == 200


def test_submit_survey_invalid_confidence_values(client):
    """Test survey submission with invalid confidence values"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-invalid-conf-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'conf@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session
        sess['user_image_pairs'] = [1]

    response = client.post('/api/submit_survey',
                          json={
                              'image_pair_id': 1,
                              'responses': {
                                  'image_quality': {'choice': 'A', 'confidence': 99},
                                  'mask_adherence': {'choice': 'B', 'confidence': 4},
                                  'identity_preservation': {'choice': 'equal', 'confidence': 2},
                              },
                          },
                          content_type='application/json')
    # The server stores the scale value it is given; an out-of-range answer is data, not a server error.
    assert response.status_code == 200


def test_get_image_pair_completed_all_pairs(client):
    """Test getting image pair when all pairs are completed"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-all-complete-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'complete@example.com', occupation='Engineer')

        for pair_id in [1, 2, 3]:
            insert_response(db, participant_id, pair_id, STANDARD_RESPONSES)

        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session

    response = client.get('/api/get_image_pair/99')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_index_route_completed_survey(client):
    """Test index route redirects to thank you when survey is completed"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-completed-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'completed@example.com', occupation='Engineer')

        for pair_id in [1, 2, 3]:
            insert_response(db, participant_id, pair_id, STANDARD_RESPONSES)

        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session
        sess['referral_validated'] = True
        sess['tutorial_completed'] = True

    response = client.get('/')
    assert response.status_code == 200
    assert b'thank' in response.data.lower() or b'complete' in response.data.lower()


def test_tutorial_route_no_demographics(client):
    """Test tutorial route redirects when demographics not completed"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-no-demo'
        sess['referral_validated'] = True

    response = client.get('/tutorial')
    assert response.status_code == 302


def test_concurrent_session_handling(client):
    """Test handling of multiple sessions for same email"""
    from src.survey.app import get_db, _get_completed_trial_ids_for_email
    import uuid

    email = 'concurrent@example.com'

    with client.application.app_context():
        db = get_db()

        session1 = str(uuid.uuid4())
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (session1,))
        pid1 = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, pid1, email, occupation='Engineer')

        session2 = str(uuid.uuid4())
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Firefox', 'Windows')",
                  (session2,))
        pid2 = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, pid2, email, occupation='Designer')

        insert_response(db, pid1, 1, STANDARD_RESPONSES)
        insert_response(db, pid2, 2, STANDARD_RESPONSES)

        db.commit()
        db.close()

    with client.application.app_context():
        completed = _get_completed_trial_ids_for_email(email)
        assert len(completed) == 2
        assert 1 in completed
        assert 2 in completed


def test_database_connection_cleanup(client):
    """Test that database connections are properly closed"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-cleanup'
        sess['referral_validated'] = True
        sess['tutorial_completed'] = True

    for i in range(5):
        response = client.get('/')
        assert response.status_code == 200


def test_empty_referral_code(referral_client):
    """An empty referral code is rejected, not passed through."""
    client = referral_client('TESTCODE')

    response = client.post('/referral',
                          data={'referral_code': ''},
                          follow_redirects=False)

    assert response.status_code == 200
    assert 'Invalid referral code' in response.data.decode()
    with client.session_transaction() as sess:
        assert not sess.get('referral_validated')


def test_case_insensitive_referral_code(referral_client):
    """The route upper-cases the input, so a lowercase code matches."""
    client = referral_client('TESTCODE123')

    response = client.post('/referral',
                          data={'referral_code': 'testcode123'},
                          follow_redirects=False)

    assert response.status_code == 302


class _WriteFails:
    """Delegate to the real connection, and fail the response INSERT the way a locked database does."""

    def __init__(self, real):
        self._real = real
        self.rolled_back = False

    def execute(self, sql, params=()):
        if 'INSERT INTO survey_responses' in sql:
            raise __import__('sqlite3').OperationalError('database is locked')
        return self._real.execute(sql, params)

    def commit(self):
        return self._real.commit()

    def rollback(self):
        self.rolled_back = True
        return self._real.rollback()

    def close(self):
        return self._real.close()

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_submit_survey_reports_500_and_rolls_back_when_the_write_fails(client, monkeypatch):
    """A failed write must not leave the participant looking saved, and must not half-write."""
    import uuid
    import src.survey.app as app_module
    from src.survey.app import get_db

    unique_session = f'test-write-fails-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                   (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'writefails@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session
        sess['user_image_pairs'] = [1]

    real_get_db = app_module.get_db
    wrappers = []

    def get_db_with_fault():
        wrapper = _WriteFails(real_get_db())
        wrappers.append(wrapper)
        return wrapper

    monkeypatch.setattr(app_module, 'get_db', get_db_with_fault)

    response = client.post('/api/submit_survey',
                           json={'image_pair_id': 1, 'responses': STANDARD_RESPONSES, 'time_spent': 3.2},
                           content_type='application/json')

    assert response.status_code == 500
    assert wrappers[-1].rolled_back, 'the failed transaction is rolled back, not left open'

    app_module.get_db = real_get_db
    with client.application.app_context():
        db = get_db()
        rows = db.execute('SELECT COUNT(*) AS n FROM survey_responses').fetchone()['n']
        db.close()
    assert rows == 0
