"""Audit F8 (2026-11-05): a referral code is a bearer token with no expiry and no record of who used
it. One posted on a participant forum admits unlimited people, and nothing ties a session to the code
that admitted it - so contaminated data cannot be traced back to a source.

The trace is a hash, never the code: audit.log is a wider-read operational file, and a plaintext code
in it is a leak of its own. Same treatment emails got in #64.
"""
import json

CODE = 'STUDY2026ALPHA'


def _log_text(tmp_path):
    log = tmp_path / 'audit.log'
    return log.read_text() if log.exists() else ''


def _entries(tmp_path):
    return [json.loads(line) for line in _log_text(tmp_path).splitlines() if line.strip()]


def test_admission_records_the_code_as_a_hash_tied_to_the_session(referral_client, tmp_path):
    from src.survey import app as app_module

    client = referral_client(CODE)
    client.get('/')  # the app mints the participant session on the home page
    with client.session_transaction() as sess:
        session_id = sess['session_id']

    response = client.post('/referral', data={'referral_code': CODE})
    assert response.status_code in (302, 303), response.get_data(as_text=True)

    text = _log_text(tmp_path)
    assert CODE not in text, 'a plaintext code in the operational log is a code leak of its own'

    entries = [e for e in _entries(tmp_path) if e['action'] == 'REFERRAL_ACCEPTED']
    assert entries, 'admission left no trace: a leaked code cannot be traced to a session'
    assert entries[0]['details']['referral_code_hash'] == app_module._pii_hash(CODE)
    assert entries[0]['session'] == session_id, 'the trace must say which session the code admitted'


def test_a_rejected_code_is_not_recorded_in_the_clear(referral_client, tmp_path):
    client = referral_client(CODE)
    client.get('/')

    client.post('/referral', data={'referral_code': 'NOT-A-CODE-9999'})

    text = _log_text(tmp_path)
    assert 'NOT-A-CODE-9999' not in text
    assert not [e for e in _entries(tmp_path) if e['action'] == 'REFERRAL_ACCEPTED']
