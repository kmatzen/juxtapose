"""A corrupt JSON cell must degrade, not cost the analyst the dashboard: results, stats and CSV all
flatten every row through one function, so one bad cell used to take all three down."""
import json

import pytest
from src.survey.app import _flatten_result
from tests.conftest import insert_demographics, insert_response

NON_OBJECTS = ['[]', '[1, 2]', '"text"', '5', 'null', 'true', '{not json', '']
JSON_COLUMNS = ['responses', 'stimulus_data', 'demographics_data']


@pytest.mark.parametrize('column', JSON_COLUMNS)
@pytest.mark.parametrize('payload', NON_OBJECTS)
def test_non_object_json_cells_degrade_to_empty_fields(column, payload):
    flat = _flatten_result({'id': 1, 'session_id': 's', column: payload})

    assert column not in flat, 'the raw column is consumed, not shown to the analyst'
    assert flat['method_a'] == '' and flat['method_b'] == ''


def test_well_formed_row_still_flattens():
    flat = _flatten_result({
        'id': 1,
        'demographics_data': json.dumps({'occupation': 'Engineer'}),
        'stimulus_data': json.dumps({'methods': {'a': 'gen5', 'b': 'gen6'},
                                     'inputs': {'seed': 7}, 'prompt': 'a red cube'}),
        'responses': json.dumps({'image_quality': {'choice': 'A', 'confidence': 4}}),
    })

    assert flat['occupation'] == 'Engineer'
    assert (flat['method_a'], flat['method_b']) == ('gen5', 'gen6')
    assert flat['input_seed'] == 7
    assert flat['prompt'] == 'a red cube'
    assert flat['image_quality_choice'] == 'A'
    assert flat['image_quality_confidence'] == 4
    assert flat['image_quality_preferred_method'] == 'gen5'


def test_non_object_inputs_cell_degrades():
    flat = _flatten_result({'id': 1, 'stimulus_data': json.dumps({'inputs': ['a', 'b']})})

    assert flat['method_a'] == ''


def _login(client):
    return client.post('/admin/login', data={'password': 'admin123'})


def _corrupt_response_row(client, raw_responses):
    from src.survey.app import get_db

    with client.application.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES ('corrupt-row', 'Chrome', 'macOS')")
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'corrupt@example.com', occupation='Engineer')
        insert_response(db, participant_id, 1, {'image_quality': {'choice': 'A', 'confidence': 3}})
        db.execute('UPDATE survey_responses SET responses = ?', (raw_responses,))
        db.commit()
        db.close()


@pytest.mark.parametrize('raw', ['[]', '"not an object"', 'null'])
def test_admin_surfaces_survive_a_corrupt_response_cell(client, raw):
    _login(client)
    _corrupt_response_row(client, raw)

    for path in ('/api/admin/results', '/api/admin/stats', '/api/admin/export'):
        response = client.get(path)
        assert response.status_code == 200, f'{path} died on row with responses={raw!r}'

    rows = client.get('/api/admin/results').get_json()['rows']
    assert rows[0]['email'] == 'corrupt@example.com'
