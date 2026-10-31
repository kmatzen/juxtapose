"""Audit F10: the admin password check should not leak by timing.

The limiter makes a real timing attack on a 10-per-hour endpoint academic, so this is a cleanup with
a guard: compare_digest is the primitive for comparing a secret, and the test asserts the check
reaches it, not that the comparison happens to be == today.
"""
import json

import hmac


def test_the_admin_password_check_is_constant_time(client, monkeypatch):
    seen = []
    real = hmac.compare_digest

    def recording(left, right):
        seen.append((left, right))
        return real(left, right)

    from src.survey import app as app_module

    monkeypatch.setattr(app_module.hmac, 'compare_digest', recording)
    client.post('/admin/login', data={'password': app_module.ADMIN_PASSWORD})
    assert seen, 'the admin password is compared with ==, which leaks a prefix match to a timing probe'
    # Bytes: compare_digest rejects non-ASCII strings, which is what locked an accented password out.
    assert seen[0] == (app_module.ADMIN_PASSWORD.encode('utf-8'),
                       app_module.ADMIN_PASSWORD.encode('utf-8'))


def test_a_wrong_password_still_fails_the_login(client):
    response = client.post('/admin/login', data={'password': 'definitely-not-it'}, follow_redirects=False)
    assert response.status_code == 401
    with client.session_transaction() as sess:
        assert not sess.get('admin_authenticated')


def test_a_non_ascii_password_still_logs_in(client, monkeypatch):
    """Audit 6 F4: compare_digest refuses non-ASCII strings, so the right password answered 500."""
    from src.survey import app as app_module
    monkeypatch.setattr(app_module, 'ADMIN_PASSWORD', 'café-passwörd')

    response = client.post('/admin/login', data={'password': 'café-passwörd'})

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get('admin_authenticated')


def test_a_wrong_non_ascii_password_is_a_clean_401_that_is_logged(client, tmp_path, monkeypatch):
    """The failure the 500 hid: no 401, no audit line, no hint the password is the problem."""
    from src.survey import app as app_module
    log_file = tmp_path / 'audit.log'
    monkeypatch.setattr('src.survey.app.AUDIT_LOG_FILE', str(log_file))
    monkeypatch.setattr(app_module, 'ADMIN_PASSWORD', 'café-passwörd')

    response = client.post('/admin/login', data={'password': 'café-passwörd?'})

    assert response.status_code == 401
    actions = [json.loads(line)['action'] for line in log_file.read_text().splitlines()]
    assert 'ADMIN_LOGIN_FAILED' in actions
