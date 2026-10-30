"""F4: behind the TLS proxy every client used to look like 127.0.0.1.

Production terminates TLS at a proxy, so the socket peer is the proxy. Without ProxyFix the
admin-login cap becomes one global 10/hour budget for the whole study, and every audit line names
the proxy instead of the person who logged in.
"""

import json

from tests.conftest import app_module

PROXY = "127.0.0.1"


def _login(client, forwarded_for=None, remote_addr=PROXY):
    headers = {} if forwarded_for is None else {"X-Forwarded-For": forwarded_for}
    return client.post(
        "/admin/login",
        data={"password": app_module.ADMIN_PASSWORD},
        headers=headers,
        environ_base={"REMOTE_ADDR": remote_addr},
    )


def _audit_entries(app_module, tmp_path):
    path = tmp_path / "audit.log"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_login_limit_is_per_forwarded_client_not_per_proxy(app, client, tmp_path):
    """Ten logins from one client behind the proxy must not lock out a different client."""
    for _ in range(11):
        _login(client, "203.0.113.9")

    victim = _login(client, "198.51.100.7")
    assert victim.status_code != 429, (
        "the admin-login budget is shared by every client behind the proxy: one person can "
        "exhaust the 10/hour cap for the whole study"
    )


def test_audit_log_names_the_real_client_ip(app, client, tmp_path):
    resp = _login(client, "203.0.113.9")
    assert resp.status_code == 302

    entries = _audit_entries(app, tmp_path)
    logins = [e for e in entries if e["action"] == "ADMIN_LOGIN_SUCCESS"]
    assert logins, f"no login audit line written, got {[e['action'] for e in entries]}"
    assert logins[-1]["ip"] == "203.0.113.9", (
        f"audit line names {logins[-1]['ip']!r} - the proxy, not the person who logged in"
    )


def test_direct_serving_without_the_header_still_works(app, client, tmp_path):
    """A study served straight to the client (no proxy) must not regress."""
    resp = _login(client, None, remote_addr="203.0.113.10")
    assert resp.status_code == 302

    entries = _audit_entries(app, tmp_path)
    logins = [e for e in entries if e["action"] == "ADMIN_LOGIN_SUCCESS"]
    assert logins[-1]["ip"] == "203.0.113.10"


def test_the_admin_page_still_loads_for_a_proxy_client(app, client):
    assert client.get("/admin/login", headers={"X-Forwarded-For": "203.0.113.9"},
                     environ_base={"REMOTE_ADDR": PROXY}).status_code == 200
