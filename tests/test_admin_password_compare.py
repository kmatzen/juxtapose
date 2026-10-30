"""Audit F10: the admin password check should not leak by timing.

The limiter makes a real timing attack on a 10-per-hour endpoint academic, so this is a cleanup with
a guard: compare_digest is the primitive for comparing a secret, and the test asserts the check
reaches it, not that the comparison happens to be == today.
"""
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
    assert seen[0] == (app_module.ADMIN_PASSWORD, app_module.ADMIN_PASSWORD)


def test_a_wrong_password_still_fails_the_login(client):
    response = client.post('/admin/login', data={'password': 'definitely-not-it'}, follow_redirects=False)
    assert response.status_code == 401
    with client.session_transaction() as sess:
        assert not sess.get('admin_authenticated')
