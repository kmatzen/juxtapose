"""
Tests for Flask routes
"""
import pytest
import json


def test_index_route(client):
    """Test the index route loads"""
    # Set up session to bypass referral and tutorial
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-index'
        sess['referral_validated'] = True
        sess['tutorial_completed'] = True
    
    response = client.get('/')
    assert response.status_code == 200
    assert b'Research Survey' in response.data


def test_api_config(client):
    """Test the config API endpoint"""
    response = client.get('/api/config')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'dev_mode' in data


def test_submit_demographics_no_session(client):
    """Test demographics submission without session returns 400"""
    response = client.post('/api/submit_demographics',
                          json={'email': 'test@example.com'},
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_submit_demographics_with_session(client, sample_demographics):
    """Test demographics submission with valid session"""
    # Create a session first
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-123'
        sess['referral_validated'] = True
    
    response = client.post('/api/submit_demographics',
                          json=sample_demographics,
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_reset_session_clears_data(client, app, monkeypatch):
    """DEV_MODE reset clears the session without touching shared module state."""
    from src.survey import app as app_module

    # Resetting via os.environ + importlib.reload() rebuilt the module and, with
    # it, its DATABASE global -- which dropped this test out of its own fixture.
    monkeypatch.setattr(app_module, 'DEV_MODE', True)

    with client.session_transaction() as sess:
        sess['session_id'] = 'test-session-456'
        sess['referral_validated'] = True
        sess['tutorial_completed'] = True

    response = client.get('/reset_session', follow_redirects=False)
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert 'referral_validated' not in sess
        assert 'tutorial_completed' not in sess


def test_tutorial_route_requires_session(client):
    """Test tutorial route redirects without session"""
    response = client.get('/tutorial')
    assert response.status_code == 302  # Redirect


def test_admin_login_requires_password(client):
    """Test admin login rejects wrong password"""
    response = client.post('/admin/login',
                          data={'password': 'wrong'},
                          follow_redirects=False)  # Don't follow redirects to check error message
    assert response.status_code == 401
    assert b'Invalid credentials' in response.data



def test_tutorial_sends_a_participant_without_demographics_to_the_intake_page(client):
    """The walkthrough gates Submit, so it must not be enterable before the intake form exists."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'tutorial-no-demographics'
        sess['referral_validated'] = True

    response = client.get('/tutorial', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].rstrip('/') == ''
