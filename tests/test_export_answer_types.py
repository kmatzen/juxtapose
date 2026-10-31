"""Audit #1, #12, #15, #16: what the analyst gets out of the answers that were collected."""
from tests.conftest import complete_intake
import csv
import io
import json

ANSWERS = {
    'image_quality': {'choice': 'A', 'confidence': 3},
    'notes': {'text': '=HYPERLINK("http://evil","click")'},
    'difficulty': {'value': 4},
    'device': {'value': 'phone'},
}


def _study_with_every_question_type(app_module):
    app_module.CONFIG['questions'] = [
        {'name': 'image_quality', 'type': 'ab_preference', 'label': 'Quality', 'confidence': True,
         'required': True, 'depends_on': None, 'section_label': 'Quality'},
        {'name': 'notes', 'type': 'free_text', 'label': 'Notes', 'confidence': False,
         'required': False, 'depends_on': None, 'section_label': 'Notes'},
        {'name': 'difficulty', 'type': 'likert', 'label': 'Difficulty', 'confidence': False,
         'required': False, 'depends_on': None, 'section_label': 'Difficulty', 'scale': 5},
        {'name': 'device', 'type': 'multiple_choice', 'label': 'Device', 'confidence': False,
         'required': False, 'depends_on': None, 'section_label': 'Device',
         'options': [{'value': 'phone', 'label': 'Phone'}, {'value': 'desktop', 'label': 'Desktop'}]},
    ]


def _one_answered_trial(client):
    with client.session_transaction() as sess:
        sess['session_id'] = 'answers-shapes'
    client.post('/api/submit_demographics', json=complete_intake(email='shapes@example.com'))
    pair = client.get('/api/get_image_pair/0').get_json()
    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'], 'responses': ANSWERS, 'time_spent': 12.0})
    assert response.status_code == 200, response.get_json()
    return pair


def _admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


def test_every_answer_type_is_in_the_export(app, client):
    from src.survey import app as app_module
    _study_with_every_question_type(app_module)
    _one_answered_trial(client)
    _admin(client)

    body = client.get('/api/admin/export').get_data(as_text=True)
    row = dict(zip(*[next(csv.reader(io.StringIO(line))) for line in body.splitlines()[:2]]))

    assert row['difficulty_value'] == '4'
    assert row['device_value'] == 'phone'
    assert 'HYPERLINK' in row['notes_text'], 'the participant wrote it, so the analyst reads it'
    assert row['image_quality_choice'] in ('A', 'B')
    assert row['image_quality_preferred_method'] not in ('', None)


def test_a_participant_answer_cannot_become_an_excel_formula(app, client):
    from src.survey import app as app_module
    _study_with_every_question_type(app_module)
    _one_answered_trial(client)
    _admin(client)

    body = client.get('/api/admin/export').get_data(as_text=True)
    cells = [cell for row in csv.reader(io.StringIO(body)) for cell in row if 'HYPERLINK' in cell]

    assert len(cells) == 1, 'the answer survives to exactly one cell'
    assert not cells[0].startswith('='), f'Excel runs this cell: {cells[0]!r}'
    assert cells[0].startswith("'"), 'the apostrophe is what tells Excel this text is text'
    assert 'HYPERLINK' in cells[0], 'guarding the cell must not delete the participant answer'


def test_results_rows_carry_the_timing_flag_the_export_has(app, client):
    from src.survey import app as app_module
    _study_with_every_question_type(app_module)
    _one_answered_trial(client)
    _admin(client)

    row = client.get('/api/admin/results').get_json()['rows'][0]
    header = next(csv.reader(io.StringIO(client.get('/api/admin/export').get_data(as_text=True))))

    assert 'timing_flag' in row, 'the table cannot filter what only the CSV reports'
    assert 'timing_flag' in header
    assert row['timing_flag'] == 0


def test_health_does_not_name_the_database(client):
    body = client.get('/health').get_json()

    assert body['status'] == 'healthy'
    assert 'database' not in body, 'an unauthenticated endpoint must not point at the answers file'
