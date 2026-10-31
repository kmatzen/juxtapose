"""Audit 6 F2/F8: the referral code admits a session to the study, so it guards the API too.

The gate redirected the pages, which is not the study: the API is. Measured on HEAD with
REFERRAL_CODES set, a session that was 302'd away posted demographics, took a trial and stored an
answer, all 200. Guessing was capped only per session, and sessions are free.
"""
from tests.conftest import complete_intake

PAIR_ANSWER = {'image_quality': {'choice': 'A', 'confidence': 4},
               'prompt_adherence': {'choice': 'B', 'confidence': 3}}

DEMOGRAPHICS = {'email': 'gate@lab.example', 'occupation': 'software-engineer',
             'technical_background': 'advanced', 'has_used_image_gen': 'regularly',
             'works_on_ai_development': 'no', 'ai_usage_frequency': 'often',
             'works_with_graphics': 'no', 'ai_familiarity': 'basic'}


def test_the_study_api_refuses_a_session_that_never_entered_a_code(referral_client):
    client = referral_client('SECRETCODE-2026')

    assert client.get('/').status_code == 302
    assert client.get('/api/config').status_code == 403
    assert client.get('/api/check_demographics').status_code == 403
    assert client.get('/api/get_image_pair/0').status_code == 403
    assert client.post('/api/submit_demographics', json=complete_intake(DEMOGRAPHICS)).status_code == 403
    assert client.post('/api/submit_survey',
                       json={'image_pair_id': 1, 'responses': {}, 'time_spent': 5}).status_code == 403
    assert client.post('/api/complete_tutorial').status_code == 403


def test_the_health_check_and_the_gate_page_stay_open(referral_client):
    client = referral_client('SECRETCODE-2026')

    assert client.get('/health').status_code == 200
    assert client.get('/referral').status_code == 200


def test_a_code_holder_still_runs_the_whole_study(referral_client):
    client = referral_client('SECRETCODE-2026')
    admitted = client.post('/referral', data={'referral_code': 'SECRETCODE-2026'},
                           follow_redirects=False)
    assert admitted.status_code == 302

    client.get('/')  # the index route mints the participant session, as it does in the browser
    assert client.post('/api/submit_demographics', json=complete_intake(DEMOGRAPHICS)).status_code == 200
    pair = client.get('/api/get_image_pair/0')
    assert pair.status_code == 200
    submitted = client.post('/api/submit_survey',
                            json={'image_pair_id': pair.get_json()['id'],
                                  'responses': PAIR_ANSWER, 'time_spent': 12})
    assert submitted.status_code == 200


def test_a_lowercase_entry_in_the_env_still_admits_a_typed_code(referral_client):
    client = referral_client('study-2026')

    assert client.post('/referral', data={'referral_code': 'study-2026'}).status_code == 302


def test_code_guessing_is_capped_per_address(referral_client):
    client = referral_client('SECRETCODE-2026')

    for i in range(20):
        assert client.post('/referral', data={'referral_code': f'GUESS-{i}'}).status_code == 200

    assert client.post('/referral', data={'referral_code': 'GUESS-20'}).status_code == 429


def test_a_refused_code_leaves_an_audit_line(referral_client, app, tmp_path, monkeypatch):
    import json

    client = referral_client('SECRETCODE-2026')
    log_file = tmp_path / 'audit.log'
    monkeypatch.setattr('src.survey.app.AUDIT_LOG_FILE', str(log_file))

    client.post('/referral', data={'referral_code': 'WRONG-CODE'})

    actions = [json.loads(line)['action'] for line in log_file.read_text().splitlines()]
    assert 'REFERRAL_REJECTED' in actions
