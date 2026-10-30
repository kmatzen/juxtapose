"""Fifth audit, findings 12 and 15: a JSON body that is not an object, and two joins that said the
same thing twice. Finding 14 lives in tests/test_trial_input_lookup.py, which has to boot a study."""
import json

import pytest


def _admin(client):
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


@pytest.mark.parametrize('body', [[], 'delete me', {'email': 5}, 7])
def test_a_body_that_is_not_an_email_object_is_refused_not_a_crash(client, app, body):
    """F12: request.json.get() raised AttributeError on a JSON string, so a hand-made delete
    request answered 500 where every other bad input gets a clean 400."""
    from src.survey import app as app_module
    admin = _admin(client)
    response = admin.post('/api/admin/delete_by_email', json=body, content_type='application/json')
    assert response.status_code == 400, response.get_data(as_text=True)[:200]
    lines = [json.loads(line) for line in
             open(app_module.AUDIT_LOG_FILE, encoding='utf-8')]
    assert len([line for line in lines if line['action'] == 'DELETE_FAILED']) == 1, (
        f'{body!r} returned 400 but wrote {len(lines)} audit lines')


def test_results_and_export_agree_on_who_answered(client, app):
    """F15: both queries said LEFT JOIN plus WHERE s.id IS NOT NULL, which is an INNER JOIN."""
    from src.survey import app as app_module
    from tests.conftest import insert_demographics, insert_response

    admin = _admin(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        try:
            answered = db.execute(
                "INSERT INTO participants (session_id) VALUES ('audit-five-answered')").lastrowid
            db.execute("INSERT INTO participants (session_id) VALUES ('audit-five-silent')")
            insert_demographics(db, answered, 'agree@example.com')
            insert_response(db, answered, 1,
                              {'image_quality': {'choice': 'A', 'confidence': 4}})
            db.commit()
        finally:
            db.close()

    rows = admin.get('/api/admin/results').get_json()['rows']
    csv_rows = admin.get('/api/admin/export').get_data(as_text=True).strip().splitlines()[1:]
    assert [row['session_id'] for row in rows] == ['audit-five-answered']
    assert len(csv_rows) == 1, f'export wrote {len(csv_rows)} rows, results wrote {len(rows)}'
