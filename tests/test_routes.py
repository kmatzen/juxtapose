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


def test_reset_session_clears_data(client):
    """Test that reset_session clears session data"""
    # DEV_MODE is false in tests, so this will trigger /reset_session_confirm flow
    # We need to set DEV_MODE to true temporarily for this test
    import os
    old_dev_mode = os.environ.get('DEV_MODE')
    os.environ['DEV_MODE'] = 'true'
    
    # Reload app to pick up DEV_MODE
    import importlib
    from src.survey import app as app_module
    importlib.reload(app_module)
    client.application = app_module.app
    
    try:
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-456'
            sess['referral_validated'] = True
            sess['tutorial_completed'] = True
        
        # Don't follow redirects - we just want to test that session is cleared
        response = client.get('/reset_session', follow_redirects=False)
        assert response.status_code == 302  # Redirect to index
        
        # Session should be cleared after the redirect
        # Note: The index route will create a new session_id if we follow the redirect,
        # but the original session data should be cleared
        with client.session_transaction() as sess:
            # The session will be empty after reset
            assert 'referral_validated' not in sess
            assert 'tutorial_completed' not in sess
            # session_id might be recreated by index route if we followed redirects,
            # but the old session_id should be gone
    finally:
        # Restore original DEV_MODE
        if old_dev_mode:
            os.environ['DEV_MODE'] = old_dev_mode
        else:
            os.environ.pop('DEV_MODE', None)
        
        # Reload app again to restore original state
        importlib.reload(app_module)
        client.application = app_module.app


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

