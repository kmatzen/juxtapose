"""Audit 6 F18: the session that owes a participant their remaining trials has to outlive the tab.

`PERMANENT_SESSION_LIFETIME` is configured at import and read by nothing: Flask writes an expiry onto
the session cookie only for a session marked permanent. Without it the cookie dies with the browser,
and so does the session id the participant's unanswered trials are stored against — the resume the
index page promises is a within-one-tab promise.
"""
from datetime import timedelta


def _session_cookie(response):
    cookies = [h for h in response.headers.getlist('Set-Cookie') if h.startswith('session=')]
    return cookies[0] if cookies else None


def test_visiting_the_study_mints_a_session_that_survives_a_browser_restart(client, app):
    cookie = _session_cookie(client.get('/'))

    assert cookie, 'the visit minted no session, so this test measured nothing'
    assert 'Max-Age' in cookie or 'Expires' in cookie, (
        f'the session dies with the tab, taking the owed trials with it: {cookie!r}')


def test_the_lifetime_the_app_configures_is_the_lifetime_the_cookie_carries(client, app):
    lifetime = app.config['PERMANENT_SESSION_LIFETIME']
    assert isinstance(lifetime, timedelta), 'the app configures no session lifetime to honour'

    cookie = _session_cookie(client.get('/'))
    max_age = [part.split('=', 1)[1] for part in cookie.split(';') if part.strip().startswith('Max-Age')]

    assert max_age and int(max_age[0]) == int(lifetime.total_seconds()), (
        f'the cookie says {max_age}, the config says {lifetime}')
