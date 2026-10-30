"""
Tests for audit finding #1 (participant data rendered in the admin dashboard)
and #16 (default admin password accepted in production).
"""
import json
import subprocess
import sys
import os


XSS_EMAIL = '<img src=x onerror="alert(1)">'


def test_demographics_rejects_html_injection_email(client):
    """A participant cannot store markup in the email the admin dashboard shows."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'xss-email-session'

    response = client.post('/api/submit_demographics',
                           json={'email': XSS_EMAIL, 'occupation': 'researcher'},
                           content_type='application/json')

    assert response.status_code == 400
    assert 'error' in json.loads(response.data)


def test_demographics_rejects_non_string_email(client):
    """A non-string email is a 400, not a crash in the audit logger."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'non-string-email-session'

    response = client.post('/api/submit_demographics',
                           json={'email': 12345, 'occupation': 'researcher'},
                           content_type='application/json')

    assert response.status_code == 400


def test_demographics_rejected_email_is_not_stored(client):
    """The rejected value must not reach the database at all."""
    from src.survey.app import get_db

    with client.session_transaction() as sess:
        sess['session_id'] = 'not-stored-session'

    client.post('/api/submit_demographics',
                json={'email': XSS_EMAIL, 'occupation': 'researcher'},
                content_type='application/json')

    db = get_db()
    try:
        rows = db.execute('SELECT email FROM demographics').fetchall()
    finally:
        db.close()

    assert XSS_EMAIL not in [r['email'] for r in rows]


def test_valid_email_still_accepted(client):
    """The guard does not break the normal path."""
    with client.session_transaction() as sess:
        sess['session_id'] = 'valid-email-session'

    response = client.post('/api/submit_demographics',
                           json={'email': 'researcher@example.com'},
                           content_type='application/json')

    assert response.status_code == 200
    assert json.loads(response.data)['success'] is True


def test_email_is_trimmed_of_whitespace(client):
    """' a@b.com ' and 'a@b.com' are the same participant for retake detection."""
    from src.survey.app import get_db

    with client.session_transaction() as sess:
        sess['session_id'] = 'trim-email-session'

    response = client.post('/api/submit_demographics',
                           json={'email': '  trim@example.com  '},
                           content_type='application/json')
    assert response.status_code == 200

    db = get_db()
    try:
        row = db.execute(
            'SELECT email FROM demographics WHERE participant_id = '
            '(SELECT id FROM participants WHERE session_id = ?)',
            ('trim-email-session',)
        ).fetchone()
    finally:
        db.close()

    assert row['email'] == 'trim@example.com'


def test_delete_by_email_rejects_non_string(client, app):
    """The admin delete endpoint validates with the same rule and does not 500."""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.post('/api/admin/delete_by_email',
                           json={'email': 42},
                           content_type='application/json')

    assert response.status_code == 400


def test_production_refuses_default_admin_password(tmp_path):
    """Audit #16: production boots must not run on the shipped default password."""
    env = dict(os.environ)
    env.update({
        'APP_ENV': 'production',

        'DATA_DIR': str(tmp_path),
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })
    env.pop('ADMIN_PASSWORD', None)

    result = subprocess.run(
        [sys.executable, '-c', 'import src.survey.app'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert 'ADMIN_PASSWORD' in result.stderr


def test_production_boots_with_real_admin_password(tmp_path):
    """The same boot succeeds once the operator sets a real password."""
    env = dict(os.environ)
    env.update({
        'APP_ENV': 'production',

        'DATA_DIR': str(tmp_path),
        'SECRET_KEY': 'a-real-secret-for-this-test',
        'ADMIN_PASSWORD': 'a-real-password-for-this-test',
        'PYTHONPATH': os.pathsep.join(sys.path),
    })

    result = subprocess.run(
        [sys.executable, '-c', 'import src.survey.app; print("booted")'],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'booted' in result.stdout


def test_a_session_from_an_older_app_version_is_cleared(client, app, monkeypatch):
    """SESSION_VERSION invalidation is what stops a deploy honouring a stale mid-study session.

    validate_session returns early when TESTING is set, so every other test runs with the hook off.
    """
    from src.survey import app as app_module

    monkeypatch.setitem(app.config, 'TESTING', False)
    with client.session_transaction() as sess:
        sess['session_id'] = 'stale-version'
        sess['version'] = app_module.SESSION_VERSION - 1

    client.get('/api/config')

    with client.session_transaction() as sess:
        assert 'session_id' not in sess


def test_a_current_session_survives_the_version_check(client, app, monkeypatch):
    """The hook clears stale sessions, not every session: a participant mid-study keeps their place."""
    from src.survey import app as app_module

    monkeypatch.setitem(app.config, 'TESTING', False)
    with client.session_transaction() as sess:
        sess['session_id'] = 'current-version'
        sess['version'] = app_module.SESSION_VERSION

    client.get('/api/config')

    with client.session_transaction() as sess:
        assert sess.get('session_id') == 'current-version'
