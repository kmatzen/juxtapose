"""The CSV export: audited, streamed, and with a header the config owns (fourth audit, F9/F16).

`admin_export` used to read every joined row into a list, flatten it into a second list, and derive
the column set from whatever keys the data happened to carry. The columns of a study that has not
been answered completely are then not the columns of one that has, and the study sits in memory
twice. A stream has to name its header before it reads a row, so the header comes from the config.
"""
import csv
import io
import json
import os
import sqlite3

from tests.conftest import app_module

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'export_snapshot.csv')

# Every configured field is filled on purpose: a sparse fixture makes the byte-identity test vacuous.
STIMULUS = {
    'methods': {'a': 'Method-A', 'b': 'Method-B'},
    'inputs': {},
    'prompt': 'a mountain landscape at sunset',
    'image_a_url': 'https://example.com/a.jpg',
    'image_b_url': 'https://example.com/b.jpg',
    'identity_urls': 'https://example.com/id.jpg',
    'mask_url': 'https://example.com/mask.jpg',
}


def _full_stimulus():
    stimulus = json.loads(json.dumps(STIMULUS))
    stimulus['inputs'] = {inp['name']: f'https://example.com/{inp["name"]}.jpg'
                          for inp in app_module.CONFIG['inputs']}
    return stimulus


def _full_demographics():
    return {field['name']: f'{field["name"]}-value' for field in app_module.CONFIG['demographics']}


def _answers(names=None):
    answered = {}
    for question in app_module.CONFIG['questions']:
        name = question['name']
        if names is not None and name not in names:
            continue
        if question['type'] == 'ab_preference':
            answered[name] = {'choice': 'A', 'confidence': 4}
        elif question['type'] == 'free_text':
            answered[name] = {'text': f'{name} answer'}
        else:
            answered[name] = {'value': 3}
    return answered


def seed_export_study(flask_app, complete=True, when='2026-01-02 03:04:05'):
    """One participant, one answered trial, with the timestamps pinned so the bytes are stable."""
    email = 'exporter@example.com'
    demographics = _full_demographics()
    demographics['email'] = email
    with flask_app.app_context():
        db = sqlite3.connect(app_module.DATABASE)
        db.row_factory = sqlite3.Row
        db.execute('INSERT INTO participants (id, session_id, referral_code, created_at, browser, '
                   'browser_version, os, screen_width, screen_height, pixel_ratio, color_depth) '
                   'VALUES (1, ? , "STUDY", ?, "Chrome", "120.0", "macOS", 1920, 1080, 2.0, 24)',
                   ('export-session', when))
        db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (1, ?, ?)',
                   (email, json.dumps(demographics)))
        stimulus = _full_stimulus()
        questions = _answers() if complete else _answers(['image_quality'])
        db.execute('INSERT INTO survey_responses (participant_id, image_pair_id, stimulus_data, '
                   'responses, was_randomized, time_spent, timing_flag, created_at) '
                   'VALUES (1, 7, ?, ?, 1, 12.5, 0, ?)',
                   (json.dumps(stimulus), json.dumps(questions), when))
        db.commit()
        db.close()


def log_in_as_admin(client):
    response = client.post('/admin/login', data={'password': app_module.ADMIN_PASSWORD},
                           follow_redirects=False)
    assert response.status_code == 302, 'the admin login must work for the export to be reachable'
    return client


def _audit_actions(tmp_path):
    path = os.path.join(str(tmp_path), 'audit.log')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [json.loads(line)['action'] for line in f if line.strip()]


def test_exporting_the_csv_leaves_an_audit_line(app, client, tmp_path):
    """Every other admin action is logged; this one copies every participant email out."""
    seed_export_study(app)
    log_in_as_admin(client)

    assert client.get('/api/admin/export').status_code == 200
    assert 'EXPORT_CSV' in _audit_actions(tmp_path), (
        'the export that ships every email address is the one admin action with no audit line')


def test_the_header_names_every_question_the_config_asks(app, client):
    """Columns are the study's, not the answers' — a partial study must not change the shape."""
    seed_export_study(app, complete=False)
    log_in_as_admin(client)

    header = next(csv.reader(io.StringIO(client.get('/api/admin/export').get_data(as_text=True))))
    for question in app_module.CONFIG['questions']:
        assert f"{question['name']}_choice" in header, (
            f"{question['name']} is a question this study asks, and its column is missing because "
            "nobody in the fixture answered it")
    for field in app_module.CONFIG['demographics']:
        assert field['name'] in header, f"the configured demographics field {field['name']} is gone"


def test_the_export_is_streamed_row_by_row(app, client):
    """The header is sent before the rows are read, which is what streaming means here."""
    seed_export_study(app)
    log_in_as_admin(client)

    response = client.get('/api/admin/export')
    chunks = [chunk for chunk in response.response if chunk]
    first = chunks[0] if isinstance(chunks[0], str) else chunks[0].decode()
    assert first.count('\n') == 1, (
        f'the first chunk carries {first.count(chr(10))} lines: the whole study is built in memory '
        'before the response starts')
    assert 'exporter@example.com' not in first
def test_the_streamed_bytes_are_the_bytes_the_dashboard_exported(app, client):
    """Byte-for-byte the same CSV (every column, every row, every _csv_safe prefix) as before."""
    seed_export_study(app)
    log_in_as_admin(client)

    # newline='': csv writes CRLF, and the default text-mode read would translate it away.
    with open(FIXTURE, encoding='utf-8', newline='') as f:
        expected = f.read()
    assert client.get('/api/admin/export').get_data(as_text=True) == expected
