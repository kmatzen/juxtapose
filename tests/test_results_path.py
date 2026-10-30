"""Audit #11: the results path carries one name per value, in the dashboard and in the CSV."""
import csv
import io
import uuid

from tests.conftest import insert_demographics, insert_response

QUESTIONS = ['image_quality', 'prompt_adherence', 'mask_adherence', 'identity_preservation']

ALL_ANSWERED = {
    'image_quality': {'choice': 'A', 'confidence': 3},
    'prompt_adherence': {'choice': 'B', 'confidence': 4},
    'mask_adherence': {'choice': 'equal', 'confidence': 2},
    'identity_preservation': {'choice': 'A', 'confidence': 5},
}

# The flat names audit #11 removes: the same three values under a second set of keys.
LEGACY_NAMES = {
    'better_image', 'image_confidence', 'preferred_method_image',
    'better_prompt_match', 'prompt_confidence', 'preferred_method_prompt',
    'better_mask_match', 'mask_confidence', 'preferred_method_mask',
    'better_identity_match', 'identity_confidence', 'preferred_method_identity',
}


def seed_study(client, session_id=None):
    """One participant who answered every question on one trial."""
    from src.survey.app import get_db

    with client.application.app_context():
        db = get_db()
        session_id = session_id or f'results-{uuid.uuid4()}'
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                   (session_id,))
        pid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, pid, 'results@example.com', occupation='Engineer')
        insert_response(db, pid, 1, ALL_ANSWERED,
                        stimulus={'prompt': 'p', 'method_a': 'Method-A', 'method_b': 'Method-B'},
                        time_spent=12.5)
        db.commit()
        db.close()
    return session_id


def as_admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True


def csv_rows(client):
    response = client.get('/api/admin/export')
    assert response.status_code == 200
    return list(csv.DictReader(io.StringIO(response.data.decode('utf-8'))))


def question_columns(header):
    return [c for c in header if c.startswith(tuple(QUESTIONS))]


def test_export_header_has_one_column_per_value(client):
    seed_study(client)
    as_admin(client)

    header = csv_rows(client)[0].keys()

    assert LEGACY_NAMES & set(header) == set()
    assert sorted(question_columns(header)) == sorted(
        f'{q}_{field}' for q in QUESTIONS for field in ('choice', 'confidence', 'preferred_method')
    )


def test_dashboard_and_csv_carry_the_same_values(client):
    seed_study(client)
    as_admin(client)

    csv_row = csv_rows(client)[0]
    dash_row = next(r for r in client.get('/api/admin/results').get_json()['rows']
                    if r.get('email') == 'results@example.com')

    for q in QUESTIONS:
        for field in ('choice', 'confidence', 'preferred_method'):
            key = f'{q}_{field}'
            assert key in dash_row, f'{key} missing from dashboard'
            assert str(dash_row[key]) == csv_row[key], f'{key} differs between dashboard and CSV'


def test_flat_submit_is_rejected(client):
    """A payload with no structured responses is a client bug, not an empty answer row."""
    from src.survey.app import IMAGE_PAIRS

    seed_study(client, 'flat-payload-session')
    with client.session_transaction() as sess:
        sess['session_id'] = 'flat-payload-session'

    response = client.post('/api/submit_survey', json={
        'image_pair_id': IMAGE_PAIRS.ids[0],
        'better_image': 'A',
        'image_confidence': 3,
    }, content_type='application/json')

    assert response.status_code == 400
