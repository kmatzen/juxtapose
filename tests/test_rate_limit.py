"""Audit #8: survey rate limits must not lock out a cohort sharing one IP."""
import pytest


class StubStore:
    """The TrialStore surface the routes use, over rows already in memory."""

    def __init__(self, rows):
        self.rows = rows
        self.ids = [row['id'] for row in rows]

    @property
    def count(self):
        return len(self.rows)

    def get(self, trial_id):
        return next((row for row in self.rows if row['id'] == trial_id), None)

    def first(self):
        return self.rows[0] if self.rows else None


def seed_participants(app_module, count, pairs=30):
    app_module.init_db()
    rows = [
        {'id': i, 'prompt': f'p{i}', 'method_a': 'Method-A', 'method_b': 'Method-B',
         'image_a_url': f'a{i}.jpg', 'image_b_url': f'b{i}.jpg',
         'mask_url': '', 'identity_urls': ''}
        for i in range(1, pairs + 1)
    ]
    app_module.CONFIG['survey']['pairs_per_user'] = pairs
    app_module.IMAGE_PAIRS = StubStore(rows)
    app_module.TUTORIAL_PAIR = rows[0]
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


def _answer_every_trial(client, trials):
    codes = []
    for _ in range(trials):
        pair = client.get('/api/get_image_pair/0')
        assert pair.status_code == 200, pair.status_code
        codes.append(client.post('/api/submit_survey', json={
            'image_pair_id': pair.get_json()['id'],
            'responses': {'image_quality': {'choice': 'A', 'confidence': 4}},
            'time_spent': 5.0}).status_code)
    return codes


def test_a_study_longer_than_the_old_hourly_cap_is_finishable(app):
    """The cap is an abuse guard, not a study-length limit: at 60 per hour the 61st trial of an
    80-pair study came back 429, and the participant could not finish the study they started."""
    from src.survey import app as app_module
    seed_participants(app_module, 1, pairs=80)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['session_id'] = 'ip-share-0'

    codes = _answer_every_trial(client, 80)
    assert codes == [200] * 80, (
        f'trial {next((i + 1 for i, c in enumerate(codes) if c != 200), None)} '
        f'came back {next((c for c in codes if c != 200), None)}')


def test_a_retake_of_the_whole_study_is_not_locked_out(app):
    """Confirming a retake wipes the participant and clears the session, and /referral mints a new
    session id; the second pass through an 80-pair study must be answerable too."""
    from src.survey import app as app_module
    seed_participants(app_module, 2, pairs=80)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['session_id'] = 'ip-share-0'
    assert _answer_every_trial(client, 80) == [200] * 80

    assert client.post('/reset_session_confirm').status_code == 302
    with client.session_transaction() as sess:
        sess['session_id'] = 'ip-share-1'
    assert _answer_every_trial(client, 80) == [200] * 80


def test_admin_login_stays_capped_per_ip(app):
    client = app.test_client()
    codes = [client.post('/admin/login', data={'password': 'wrong'}).status_code
             for _ in range(12)]

    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]
