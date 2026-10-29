"""Audit #8: survey rate limits must not lock out a cohort sharing one IP."""
import pytest


def seed_participants(app_module, count):
    app_module.init_db()
    app_module.IMAGE_PAIRS = [
        {'id': i, 'prompt': f'p{i}', 'method_a': 'Method-A', 'method_b': 'Method-B',
         'image_a_url': f'a{i}.jpg', 'image_b_url': f'b{i}.jpg',
         'mask_url': '', 'identity_urls': ''}
        for i in range(1, 31)
    ]
    app_module.TUTORIAL_PAIR = app_module.IMAGE_PAIRS[0]
    db = app_module.get_db()
    try:
        for n in range(count):
            db.execute("INSERT INTO participants (session_id) VALUES (?)", (f'ip-share-{n}',))
            pid = db.execute("SELECT id FROM participants WHERE session_id = ?",
                             (f'ip-share-{n}',)).fetchone()['id']
            db.execute("INSERT INTO demographics (participant_id, email, data) VALUES (?,?,?)",
                       (pid, f'ip-share-{n}@example.com', '{}'))
        db.commit()
    finally:
        db.close()


def test_cohort_behind_one_ip_finishes_30_trials_each(app):
    from src.survey import app as app_module
    seed_participants(app_module, 3)

    for n in range(3):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['session_id'] = f'ip-share-{n}'

        for i in range(30):
            pair = client.get(f'/api/get_image_pair/{i}')
            assert pair.status_code == 200, f'session {n} trial {i}: {pair.status_code}'
            submitted = client.post('/api/submit_survey', json={
                'image_pair_id': pair.get_json()['id'],
                'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
            }, content_type='application/json')
            assert submitted.status_code == 200, f'session {n} trial {i}: {submitted.status_code}'


def test_admin_login_stays_capped_per_ip(app):
    client = app.test_client()
    codes = [client.post('/admin/login', data={'password': 'wrong'}).status_code
             for _ in range(12)]

    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]
