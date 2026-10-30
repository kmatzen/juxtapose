"""Audit 6 F13: the admin list and the CSV export read the answers through one query.

`_ADMIN_RESULTS_SELECT` restated the export's SELECT list and FROM clause verbatim. Two literals for
one row shape drift the moment someone adds a column to one of them, and the drift shows up as the
dashboard and the analyst's CSV disagreeing about what was collected.
"""
import csv
import io

from src.survey import app as app_module
from tests.conftest import insert_demographics, insert_response

ANSWERS = {'image_quality': {'choice': 'A', 'confidence': 4}}


def test_the_results_query_is_the_export_query():
    """One source for the row the dashboard shows and the export streams."""
    assert app_module._ADMIN_RESULTS_SELECT == 'SELECT' + app_module._EXPORT_SELECT + app_module._EXPORT_FROM, (
        'the admin list carries its own copy of the export query, so the two can drift apart')


def _seed_two_participants(client):
    from src.survey.app import get_db

    with client.application.app_context():
        db = get_db()
        for index, email in enumerate(['one@example.com', 'two@example.com']):
            db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                       (f'agree-{index}',))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            insert_demographics(db, participant_id, email, occupation='Engineer')
            insert_response(db, participant_id, 1, ANSWERS)
        db.commit()
        db.close()


def _admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


def test_the_dashboard_page_and_the_export_cover_the_same_answers(client):
    _seed_two_participants(client)
    client = _admin(client)

    page = client.get('/api/admin/results').get_json()
    exported = list(csv.DictReader(io.StringIO(client.get('/api/admin/export').get_data(as_text=True))))

    assert page['total'] == len(exported) == 2, (page['total'], len(exported))
    assert {row['session_id'] for row in page['rows']} == {row['session_id'] for row in exported}, (
        'the dashboard page and the CSV disagree about whose answers are in the study')
