"""F5 (fourth audit): `required: true` on a free_text question has to mean something.

Three places disagreed: the template rendered the textarea with no `required` attribute (the likert
and multiple-choice branches add one), the page always posted `{text: ''}` for an empty box, and the
server's completeness rule asked only `if not q_resp` — a dict holding an empty string is truthy.
The study then reported every trial finished with the qualitative answer blank.
"""
import json
import re
import uuid

from tests.conftest import insert_demographics

REQUIRED_TEXT = [{'name': 'why', 'type': 'free_text', 'label': 'Why?', 'required': True}]


def _answer_for(client, monkeypatch, email, pair_id, text):
    """One answered trial under a study whose only question is a required free text."""
    from src.survey.app import get_db
    from src.survey import app as app_module

    monkeypatch.setitem(app_module.CONFIG, 'questions', REQUIRED_TEXT)
    session_id = f'freetext-{uuid.uuid4()}'
    with client.application.app_context():
        db = get_db()
        db.execute('INSERT INTO participants (session_id, browser, os) VALUES (?, ?, ?)',
                   (session_id, 'Chrome', 'macOS'))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, email)
        db.execute('INSERT INTO survey_responses '
                   '(participant_id, image_pair_id, stimulus_data, responses, was_randomized, time_spent) '
                   'VALUES (?, ?, ?, ?, 0, 9)',
                   (participant_id, pair_id, '{}', json.dumps({'why': {'text': text}})))
        db.commit()
        db.close()
    return app_module._get_completed_trial_ids(participant_id)


def test_a_blank_required_free_text_is_not_a_completed_trial(client, app, monkeypatch):
    completed = _answer_for(client, monkeypatch, 'blank@example.com', 7, '')
    assert 7 not in completed, 'a blank required answer counted as a finished trial'


def test_a_written_required_free_text_completes_the_trial(client, app, monkeypatch):
    completed = _answer_for(client, monkeypatch, 'written@example.com', 7, 'because sharp edges')
    assert 7 in completed


def test_the_rendered_textarea_carries_the_required_attribute(client, app, monkeypatch):
    from src.survey import app as app_module
    monkeypatch.setitem(app_module.CONFIG, 'questions', REQUIRED_TEXT)

    page = client.get('/').get_data(as_text=True)
    textarea = re.search(r'<textarea[^>]*name="why_text"[^>]*>', page)
    assert textarea, 'the free_text question rendered no textarea'
    assert 'required' in textarea.group(0), textarea.group(0)
