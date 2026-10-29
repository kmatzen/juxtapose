"""A mid-study reload must resume on the trials the participant still owes, not from trial 1."""
import uuid

from src.survey.app import CONFIG, get_db


def make_participant(client):
    session = f'resume-{uuid.uuid4()}'
    db = get_db()
    try:
        cursor = db.execute('INSERT INTO participants (session_id) VALUES (?)', (session,))
        db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                   (cursor.lastrowid, f'{session}@example.com', '{}'))
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess['session_id'] = session
    return session


def serve(client, index=0):
    response = client.get(f'/api/get_image_pair/{index}')
    assert response.status_code == 200
    return response.get_json()


def answer(client, pair):
    answers = {q['name']: {'choice': 'A', 'confidence': 4}
               for q in CONFIG['questions']
               if (q.get('required') or q['type'] == 'ab_preference') and not q.get('depends_on')}
    response = client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'],
        'responses': answers,
    }, content_type='application/json')
    assert response.status_code == 200


def test_reload_serves_a_trial_the_participant_has_not_answered(client):
    make_participant(client)
    first = serve(client)
    answer(client, first)

    # The reloaded browser keeps its session cookie and replays the assignment from index 0.
    assert serve(client)['id'] != first['id']


def test_the_served_pair_reports_the_position_in_the_study(client):
    make_participant(client)
    assigned = serve(client)['total_trials']
    assert assigned > 2, 'the study fixture needs several trials to prove resume'

    answer(client, serve(client))

    resumed = serve(client)
    assert resumed['total_trials'] == assigned, 'the study size must not shrink'
    assert resumed['trials_remaining'] == assigned - 1


def test_a_fresh_session_is_not_shifted_by_the_resume_filter(client):
    make_participant(client)
    served = [serve(client, i)['id'] for i in range(serve(client)['total_trials'])]

    assert len(served) == len(set(served)), 'a fresh session must be served distinct trials'
