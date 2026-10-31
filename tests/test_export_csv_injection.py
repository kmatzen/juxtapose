"""Audit 6 F15: the export guard fires on the characters the spreadsheet evaluates on.

`_csv_safe` prefixed `= + - @` and passed a leading tab or carriage return through untouched. Both are
in the same trigger set: Excel and Google Sheets evaluate a cell whose text starts with them, and the
cell's author is a survey participant.
"""
import csv
import io

import pytest

from tests.test_export_answer_types import _admin, _study_with_every_question_type

TRIGGERS = ['=', '+', '-', '@', '\t', '\r']


@pytest.mark.parametrize('trigger', TRIGGERS)
def test_a_cell_starting_with_a_spreadsheet_trigger_is_not_a_formula(app, client, trigger):
    from src.survey import app as app_module
    _study_with_every_question_type(app_module)
    with client.session_transaction() as sess:
        sess['session_id'] = f'injection-{ord(trigger)}'

    client.post('/api/submit_demographics', json={'email': 'inj@example.com', 'occupation': 'eng'})
    pair = client.get('/api/get_image_pair/0').get_json()
    submitted = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'responses': {'image_quality': {'choice': 'A', 'confidence': 3},
                      'notes': {'text': f'{trigger}1+1'}},
        'time_spent': 5.0})
    assert submitted.status_code == 200, submitted.get_json()
    _admin(client)

    cells = [cell
             for row in csv.reader(io.StringIO(client.get('/api/admin/export').get_data(as_text=True)))
             for cell in row if '1+1' in cell]

    assert cells, 'the participant answer never reached the export, so the guard is unmeasured'
    assert cells[0].startswith("'"), f'the spreadsheet evaluates this cell: {cells[0]!r}'
