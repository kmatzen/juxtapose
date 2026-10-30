"""Audit F11: audit.log is an operational file - wider readership than the database - and a
participant email is PII. The delete-by-email actions recorded the address in plaintext.

A stable hash keeps the log useful: two lines about the same participant still join, abuse triage
still has the IP, and nobody reading the log can read out who is in the study.
"""
import json

EMAIL = 'participant-victim@example.com'


def _entries(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _delete(client, value):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client.post('/api/admin/delete_by_email', json={'email': value})


def test_a_deleted_email_never_reaches_the_audit_log(client, app, tmp_path):
    _delete(client, EMAIL)
    log = tmp_path / 'audit.log'
    text = log.read_text()
    assert EMAIL not in text, 'the participant address is copied into the operational log'
    assert 'participant-victim' not in text

    entries = [e for e in _entries(log) if e['action'].startswith('DELETE')]
    assert entries, 'the delete attempt was not audited at all'
    recorded = entries[0]['details'].get('email', '')
    assert recorded and recorded != EMAIL and '@' not in recorded
    assert entries[0]['ip'], 'abuse triage needs the IP, and it is not PII of a study participant'


def test_the_same_address_hashes_to_the_same_value(client, app, tmp_path):
    _delete(client, EMAIL)
    _delete(client, EMAIL)
    entries = [e for e in _entries(tmp_path / 'audit.log') if e['action'].startswith('DELETE')]
    assert len(entries) >= 2
    assert entries[0]['details']['email'] == entries[1]['details']['email'], 'the log must stay joinable'


def test_a_rejected_email_is_not_stored_as_plain_text(client, app, tmp_path):
    _delete(client, 'not-an-email@')
    text = (tmp_path / 'audit.log').read_text()
    assert 'not-an-email@' not in text


def test_audit_entries_are_stamped_in_utc(client, app, tmp_path):
    """The database stamps rows with CURRENT_TIMESTAMP, which is UTC. An entry stamped in server-local
    time cannot be lined up with the row it explains, and the gap is the server's UTC offset."""
    from datetime import datetime, timedelta, timezone

    from src.survey import app as app_module

    _delete(client, EMAIL)

    entry = _entries(tmp_path / 'audit.log')[-1]
    stamped = datetime.fromisoformat(entry['timestamp'])
    assert stamped.tzinfo is not None, 'a naive stamp is server-local and cannot be joined to the DB'
    assert stamped.utcoffset() == timedelta(0), entry['timestamp']

    db = app_module.get_db()
    try:
        db_now = datetime.fromisoformat(db.execute('SELECT CURRENT_TIMESTAMP AS t').fetchone()['t'])
    finally:
        db.close()
    drift = abs((stamped.astimezone(timezone.utc).replace(tzinfo=None) - db_now).total_seconds())
    assert drift <= 2, f'log and database clocks differ by {drift}s'
