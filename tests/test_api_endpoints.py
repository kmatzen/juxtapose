"""
Tests for API endpoints
"""
import pytest
import json
from tests.conftest import insert_demographics, insert_response


def test_check_demographics_no_session(client):
    """Test check_demographics without session"""
    response = client.get('/api/check_demographics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['submitted'] is False


def test_check_demographics_no_participant(client):
    """Test check_demographics with session but no participant"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'nonexistent-session'

    response = client.get('/api/check_demographics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['submitted'] is False


def test_check_demographics_with_data(client):
    """Test check_demographics with completed demographics"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-session-check-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'test@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session

    response = client.get('/api/check_demographics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['submitted'] is True
    assert data['completed_pairs'] == 0


def test_complete_tutorial_no_session(client):
    """Test complete_tutorial without session"""
    response = client.post('/api/complete_tutorial')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_complete_tutorial_with_session(client):
    """Test complete_tutorial with session"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-tutorial'

    response = client.post('/api/complete_tutorial')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True

    with client.session_transaction() as sess:
        assert sess.get('tutorial_completed') is True


def test_get_image_pair_no_session(client):
    """Test get_image_pair without session"""
    response = client.get('/api/get_image_pair/0')
    assert response.status_code in [200, 400]


def test_get_image_pair_no_email(client):
    """Test get_image_pair with session but no email"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-no-email'

    response = client.get('/api/get_image_pair/0')
    assert response.status_code in [200, 400]


def test_get_image_pair_valid(client):
    """Test get_image_pair with valid session and email"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-session-pair-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'pair@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session

    response = client.get('/api/get_image_pair/0')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'id' in data
    assert 'prompt' in data
    assert 'method_a' in data
    assert 'method_b' in data


def test_get_image_pair_out_of_range(client):
    """Test get_image_pair with invalid index"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-session-range-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'range@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session

    response = client.get('/api/get_image_pair/9999')
    assert response.status_code in [400, 404]
    data = json.loads(response.data)
    assert 'error' in data


def test_submit_survey_no_session(client):
    """Test submit_survey without session"""
    response = client.post('/api/submit_survey',
                          json={'image_pair_id': 1},
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_submit_survey_missing_fields(client):
    """Test submit_survey with missing required fields"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-submit'

    response = client.post('/api/submit_survey',
                          json={'better_image': 'A'},
                          content_type='application/json')
    assert response.status_code in [400, 404]
    if response.status_code != 404:
        data = json.loads(response.data)
        assert 'error' in data


def test_submit_survey_valid(client):
    """Test submit_survey with valid data"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-session-submit-valid-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'submit@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session

    # Submit using flat format (backward compat)
    response = client.post('/api/submit_survey',
                          json={
                              'image_pair_id': 1,
                              'better_image': 'A',
                              'image_confidence': 3,
                              'better_mask_match': 'B',
                              'mask_confidence': 4,
                              'better_identity_match': 'Equal',
                              'identity_confidence': 2,
                              'time_spent': 45.5
                          },
                          content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'completed' in data


def test_referral_get(client):
    """Test referral page GET"""
    response = client.get('/referral')
    assert response.status_code in [200, 302]


def test_referral_post_invalid_code(client):
    """Test referral page POST with invalid code"""
    import os
    old_codes = os.environ.get('REFERRAL_CODES')
    os.environ['REFERRAL_CODES'] = 'TESTCODE123'

    import importlib
    from src.survey import app as app_module
    importlib.reload(app_module)
    client.application = app_module.app

    try:
        response = client.post('/referral',
                              data={'referral_code': 'WRONGCODE'},
                              follow_redirects=False)
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert b'Invalid' in response.data or b'error' in response.data.lower()
    finally:
        if old_codes:
            os.environ['REFERRAL_CODES'] = old_codes
        else:
            os.environ.pop('REFERRAL_CODES', None)
        importlib.reload(app_module)
        client.application = app_module.app


def test_referral_post_valid_code(client):
    """Test referral page POST with valid code"""
    import os
    old_codes = os.environ.get('REFERRAL_CODES')
    os.environ['REFERRAL_CODES'] = 'TESTCODE123'

    import importlib
    from src.survey import app as app_module
    importlib.reload(app_module)
    client.application = app_module.app

    try:
        response = client.post('/referral',
                              data={'referral_code': 'TESTCODE123'},
                              follow_redirects=False)
        assert response.status_code in [302, 400]

        if response.status_code == 302:
            with client.session_transaction() as sess:
                assert sess.get('referral_validated') is True
                assert sess.get('referral_code') == 'TESTCODE123'
    finally:
        if old_codes:
            os.environ['REFERRAL_CODES'] = old_codes
        else:
            os.environ.pop('REFERRAL_CODES', None)
        importlib.reload(app_module)
        client.application = app_module.app
