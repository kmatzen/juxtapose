"""
Tests for security headers, DB isolation, and admin auth hardening.
"""
import os


def test_security_headers_present(client):
    """Every response carries the baseline security headers."""
    response = client.get('/api/config')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_test_db_is_isolated(app):
    """The test fixture's temp DB is actually used, not the repo survey.db.

    Regression guard: get_db() must honor app.config['DATABASE'].
    """
    from src.survey import app as app_module
    configured = app.config.get('DATABASE')
    assert configured is not None
    with app.app_context():
        db = app_module.get_db()
        try:
            # sqlite exposes the file backing the 'main' database.
            row = db.execute('PRAGMA database_list').fetchall()
            main_path = next(r[2] for r in row if r[1] == 'main')
        finally:
            db.close()
    assert os.path.abspath(main_path) == os.path.abspath(configured)
    assert not main_path.endswith('/survey.db') or main_path == configured


def test_admin_login_wrong_password_is_rejected(client):
    """Constant-time comparison still rejects an incorrect password."""
    response = client.post('/admin/login',
                           data={'password': 'definitely-not-the-password'},
                           follow_redirects=False)
    assert response.status_code == 401


def test_admin_login_empty_password_is_rejected(client):
    """A missing password must not authenticate."""
    response = client.post('/admin/login', data={}, follow_redirects=False)
    assert response.status_code == 401
