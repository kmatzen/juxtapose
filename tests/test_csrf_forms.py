"""The forms in the app must carry the CSRF token, with the gate left ON (fourth audit, F1/F6).

Every other suite runs with WTF_CSRF_ENABLED off, so a form posted without a token passed CI and
returned 400 to the participant. These tests read the token off the rendered page, as the browser
does, and one of them asserts the refusal is real: a post with no token must be rejected.
"""
import uuid

from tests.conftest import csrf_token
from tests.conftest import insert_demographics


def _participant_with_answers(csrf_app, client):
    """A session that has finished demographics and answered a trial: what the confirm deletes."""
    from src.survey.app import get_db

    session_id = f'csrf-reset-{uuid.uuid4()}'
    with csrf_app.app_context():
        db = get_db()
        db.execute("INSERT INTO participants (session_id, browser, os) VALUES (?, 'Chrome', 'macOS')",
                   (session_id,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, 'reset-csrf@example.com', occupation='Engineer')
        db.execute('INSERT INTO survey_responses '
                   '(participant_id, image_pair_id, stimulus_data, responses) VALUES (?, 1, ?, ?)',
                   (participant_id, '{}', '{}'))
        db.commit()
        db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session_id


def _answers_left(csrf_app):
    from src.survey.app import get_db
    with csrf_app.app_context():
        db = get_db()
        rows = db.execute('SELECT COUNT(*) FROM demographics WHERE email = ?',
                          ('reset-csrf@example.com',)).fetchone()[0]
        db.close()
    return rows


def test_the_start_over_form_offers_a_csrf_token(csrf_app, csrf_client):
    """The confirm page must hand back a token, or the button under it can only ever fail."""
    _participant_with_answers(csrf_app, csrf_client)

    page = csrf_client.get('/reset_session')
    assert page.status_code == 200
    assert csrf_token(page), 'no token to post back'


def test_the_start_over_button_resets_the_session(csrf_app, csrf_client):
    """The whole participant path: read the page, press the button, the data is gone."""
    _participant_with_answers(csrf_app, csrf_client)

    token = csrf_token(csrf_client.get('/reset_session'))
    response = csrf_client.post('/reset_session_confirm', data={'csrf_token': token},
                                follow_redirects=False)
    assert response.status_code == 302, 'form refused: ' + response.get_data(as_text=True)[:120]
    assert _answers_left(csrf_app) == 0, 'the confirmed reset kept the participant data'


def test_a_post_without_the_token_is_refused(csrf_app, csrf_client):
    """The fixture is real: with CSRF on, a tokenless post is rejected, not served."""
    _participant_with_answers(csrf_app, csrf_client)
    csrf_client.get('/reset_session')

    response = csrf_client.post('/reset_session_confirm', data={})
    assert response.status_code == 400
    assert b'CSRF token is missing' in response.data
    assert _answers_left(csrf_app) == 1, 'a refused post must not have deleted anything'


CODE = 'STUDY2024'


def test_the_referral_button_posts_with_its_token(referral_client):
    client = referral_client(CODE, csrf_enabled=True)
    token = csrf_token(client.get('/referral'))

    response = client.post('/referral', data={'csrf_token': token, 'referral_code': CODE},
                           follow_redirects=False)
    assert response.status_code == 302, 'form refused: ' + response.get_data(as_text=True)[:120]
    with client.session_transaction() as sess:
        assert sess.get('referral_validated') is True, 'a good post must admit the participant'


def test_a_referral_post_without_the_token_is_refused(referral_client):
    client = referral_client(CODE, csrf_enabled=True)
    client.get('/referral')

    response = client.post('/referral', data={'referral_code': CODE})
    assert response.status_code == 400
    with client.session_transaction() as sess:
        assert not sess.get('referral_validated'), 'a refused post admitted the participant'
