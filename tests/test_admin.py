"""
Tests for admin functionality
"""
import pytest
import json
import io
from tests.conftest import insert_demographics, insert_response

STANDARD_RESPONSES = {
    'image_quality': {'choice': 'A', 'confidence': 3},
    'mask_adherence': {'choice': 'B', 'confidence': 4},
    'identity_preservation': {'choice': 'equal', 'confidence': 2},
}


def test_admin_requires_authentication(client):
    """Test admin page requires authentication"""
    response = client.get('/admin')
    assert response.status_code == 302


def test_admin_login_get(client):
    """Test admin login page GET"""
    response = client.get('/admin/login')
    assert response.status_code == 200
    assert b'Admin Login' in response.data or b'Password' in response.data


def test_admin_login_success(client):
    """Test successful admin login"""
    response = client.post('/admin/login',
                          data={'password': 'admin123'},
                          follow_redirects=False)
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert sess.get('admin_authenticated') is True


def test_admin_logout(client):
    """Test admin logout"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/admin/logout', follow_redirects=False)
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert 'admin_authenticated' not in sess


def test_admin_page_with_auth(client):
    """Test admin page with authentication"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/admin')
    assert response.status_code == 200


def test_admin_export_csv_no_auth(client):
    """Test CSV export requires authentication"""
    response = client.get('/api/admin/export')
    assert response.status_code == 302


def test_admin_export_csv_with_auth(client):
    """Test CSV export with authentication"""
    from src.survey.app import get_db
    import uuid

    with client.application.app_context():
        db = get_db()
        unique_session = f'test-export-{uuid.uuid4()}'
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'export@example.com', occupation='Engineer')
        insert_response(db, participant_id, 1, STANDARD_RESPONSES)
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/export')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
    assert b'email' in response.data
    assert b'export@example.com' in response.data


def test_admin_delete_by_email_no_auth(client):
    """Test delete by email requires authentication"""
    response = client.post('/api/admin/delete_by_email',
                          json={'email': 'test@example.com'},
                          content_type='application/json')
    assert response.status_code == 302


def test_admin_delete_by_email_no_email_provided(client):
    """Test delete requires email parameter"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.post('/api/admin/delete_by_email',
                          json={},
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_admin_delete_by_email_invalid_email(client):
    """Test delete with invalid email format"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.post('/api/admin/delete_by_email',
                          json={'email': 'not-an-email'},
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_admin_delete_by_email_nonexistent(client):
    """Test delete with email that doesn't exist"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.post('/api/admin/delete_by_email',
                          json={'email': 'nonexistent@example.com'},
                          content_type='application/json')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_admin_delete_by_email_success(client):
    """Test successful delete by email"""
    from src.survey.app import get_db
    import uuid

    unique_email = f'delete-{uuid.uuid4()}@example.com'
    with client.application.app_context():
        db = get_db()
        unique_session = f'test-delete-{uuid.uuid4()}'
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, unique_email, occupation='Engineer')
        insert_response(db, participant_id, 1, STANDARD_RESPONSES)
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.post('/api/admin/delete_by_email',
                          json={'email': unique_email},
                          content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['participants_deleted'] == 1

    with client.application.app_context():
        db = get_db()
        result = db.execute("SELECT COUNT(*) as count FROM demographics WHERE email = ?",
                           (unique_email,)).fetchone()
        assert result['count'] == 0
        db.close()


def test_admin_rate_limiting(client):
    """Test rate limiting on admin login"""
    for i in range(3):
        response = client.post('/admin/login',
                              data={'password': f'wrong{i}'},
                              follow_redirects=False)
        assert response.status_code == 401


def test_reset_session_confirm_page(client):
    """Test reset_session_confirm page (via GET /reset_session)"""
    with client.session_transaction() as sess:
        sess['session_id'] = 'test-reset-page'

    response = client.get('/reset_session')
    assert response.status_code == 200
    assert b'Start Over' in response.data or b'confirm' in response.data.lower()


def test_reset_session_confirm_post(client):
    """Test reset_session_confirm POST deletes data"""
    from src.survey.app import get_db
    import uuid

    unique_session = f'test-reset-post-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                  (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'reset@example.com', occupation='Engineer')
        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['session_id'] = unique_session
        sess['referral_validated'] = True

    response = client.post('/reset_session_confirm', follow_redirects=False)
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert 'referral_validated' not in sess
