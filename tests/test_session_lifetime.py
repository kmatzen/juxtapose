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
    """Flask writes `Expires`, not `Max-Age`: the configured lifetime reaches the cookie as a date."""
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    lifetime = app.config['PERMANENT_SESSION_LIFETIME']
    assert isinstance(lifetime, timedelta), 'the app configures no session lifetime to honour'

    cookie = _session_cookie(client.get('/'))
    expires = [part.split('=', 1)[1].strip() for part in cookie.split(';') if part.strip().startswith('Expires')]

    assert expires, f'the cookie carries no expiry, so the configured {lifetime} is inert: {cookie!r}'
    seconds = (parsedate_to_datetime(expires[0]).astimezone(timezone.utc)
               - datetime.now(timezone.utc)).total_seconds()
    assert abs(seconds - lifetime.total_seconds()) < 60, (
        f'the cookie expires in {seconds:.0f}s, the config says {lifetime.total_seconds():.0f}s')
