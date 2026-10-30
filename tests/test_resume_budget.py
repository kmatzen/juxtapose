"""F7: a returning participant is told how many pairs they still owe, not the study size.

The assignment budget used to ignore what the participant's email had already answered, so a
returner was handed a fresh `pairs_per_user` batch and the completion gate (which counts by email)
stopped them part-way through it: shown 30, cut off at 20/30.
"""
import importlib
import uuid

import pytest

from src.survey.app import CONFIG, get_db


def _write_pairs(path, count):
    rows = ['\t'.join([f'pair {i}', 'Method-A', 'Method-B',
                       f'https://example.com/{i}-a.jpg', f'https://example.com/{i}-b.jpg',
                       f'https://example.com/{i}-mask.jpg', f'https://example.com/{i}-id.jpg'])
            for i in range(1, count + 1)]
    path.write_text('\n'.join(rows) + '\n', encoding='utf-8')


@pytest.fixture
def long_study(tmp_path, monkeypatch):
    """40 trials with the shipped pairs_per_user of 30. The file must be longer than the cap: with
    exactly 30 trials the min() in the assignment hides the budget bug, and the test passes pre-fix.
    """
    pairs = tmp_path / 'pairs.tsv'
    _write_pairs(pairs, 40)
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(pairs))

    from src.survey import app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'survey.db'))
    monkeypatch.setattr(app_module, 'AUDIT_LOG_FILE', str(tmp_path / 'audit.log'))
    app_module.app.config.update({'TESTING': True, 'SECRET_KEY': 'k', 'WTF_CSRF_ENABLED': False})
    with app_module.app.app_context():
        app_module.init_db()
    return app_module


def join_study(app_module, email):
    """One session of the study: a brand-new session cookie carrying the email used before."""
    session_id = f'resume-{uuid.uuid4()}'
    client = app_module.app.test_client()
    with app_module.app.app_context():
        db = get_db()
        try:
            cursor = db.execute('INSERT INTO participants (session_id) VALUES (?)', (session_id,))
            db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                       (cursor.lastrowid, email, '{}'))
            db.commit()
        finally:
            db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session_id
    return client


def serve(client, index=0):
    response = client.get(f'/api/get_image_pair/{index}')
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    return response.get_json()


def answer(client, pair):
    answers = {q['name']: {'choice': 'A', 'confidence': 4}
               for q in CONFIG['questions']
               if (q.get('required') or q['type'] == 'ab_preference') and not q.get('depends_on')}
    response = client.post('/api/submit_survey',
                           json={'image_pair_id': pair['id'], 'responses': answers},
                           content_type='application/json')
    assert response.status_code == 200, response.get_data(as_text=True)[:200]


def answer_trials(client, count):
    """Serving index 0 keeps returning the first pair this session has not answered."""
    for _ in range(count):
        answer(client, serve(client))


def test_a_returning_participant_is_told_what_they_still_owe(long_study):
    email = 'returner@example.com'
    answer_trials(join_study(long_study, email), 10)

    resumed = serve(join_study(long_study, email))
    assert resumed['total_pairs'] == 20, (
        f"the resumed session is told {resumed['total_pairs']} pairs: the 10 already answered are "
        "not deducted from the assignment, so the study serves past its own pairs_per_user cap")


def test_the_resumed_study_ends_where_it_says(long_study):
    email = 'finisher@example.com'
    answer_trials(join_study(long_study, email), 10)

    client = join_study(long_study, email)
    last = None
    for _ in range(20):
        last = serve(client)
        answer(client, last)

    current = last['total_pairs'] - last['trials_remaining'] + 1
    assert (current, last['total_pairs']) == (20, 20), (
        f'the last trial answered is {current}/{last["total_pairs"]}: the participant is cut off '
        "with pairs of their assignment still unserved")
    assert 'thank' in client.get('/').get_data(as_text=True).lower()


def test_a_first_time_participant_is_still_told_the_whole_study(long_study):
    assert serve(join_study(long_study, 'fresh@example.com'))['total_pairs'] == 30


def test_the_stored_rows_never_pass_the_study_cap(long_study):
    email = 'cap@example.com'
    answer_trials(join_study(long_study, email), 10)
    answer_trials(join_study(long_study, email), 20)

    with long_study.app.app_context():
        db = get_db()
        try:
            rows = db.execute(
                'SELECT COUNT(*) FROM survey_responses r JOIN demographics d '
                'ON d.participant_id = r.participant_id WHERE d.email = ?', (email,)).fetchone()[0]
        finally:
            db.close()
    assert rows == 30, f'{email} has {rows} stored trials, the study cap is 30'
