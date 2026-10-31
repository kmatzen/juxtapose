"""Audit 6 F3: progress is this session's own work, not a count keyed on an email.

Completion was answered by counting every answer stored under the participant's email address.
When there is no email - a study that collects none (anonymity is a legitimate research request),
or an intake posted without one - the count is empty forever: the participant answers every trial
they are shown, `completed` stays false, the next pair request 404s, `/` re-serves an answered
trial, and the loop repeats. The email stays what it was for: retake detection.
"""
import pytest

from src.survey import app as app_module
from tests.conftest import _boot_app


def answers_for_study():
    """Every question the booted study asks: submit_survey rejects answers to questions it does not ask."""
    return {q['name']: {'choice': 'A', 'confidence': 4}
            for q in app_module.CONFIG['questions']
            if q.get('required') or q['type'] == 'ab_preference'}

QUESTIONS = """  - name: image_quality
    type: ab_preference
    label: "Which looks better?"
    confidence: true
    required: true
  - name: prompt_adherence
    type: ab_preference
    label: "Which fits the prompt?"
    confidence: true
    required: true
"""

STUDY = """
survey:
  title: "No-email study"
  pairs_per_user: 2
demographics:
{demographics}
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - name: prompt
    type: text
    column: prompt
outputs:
  - name: image
    type: image
    column_a: image_a_url
    column_b: image_b_url
questions:
{questions}
"""

EMAIL_OPTIONAL = """  - name: email
    type: email
    label: "Email"
"""

SELECT_FIELD = """  - name: occupation
    type: select
    label: "Occupation"
    required: true
    options:
      - value: engineer
        label: Engineer
"""

ROWS = ''.join(
    f'prompt {i}\tMethod-A\tMethod-B\thttps://x/{i}a.png\thttps://x/{i}b.png\t\t\n'
    for i in range(3))


def study_client(tmp_path, monkeypatch, demographics):
    """Boot the app on a study of the test's own, the way conftest boots it for the suite."""
    (tmp_path / 'survey_config.yaml').write_text(
        STUDY.format(demographics=demographics, questions=QUESTIONS), encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(ROWS, encoding='utf-8')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    return _boot_app(tmp_path, monkeypatch, csrf_enabled=False).test_client()


def run_study(client, demographics_payload):
    """Walk the study the way the page does, and report what the last submit said."""
    client.get('/')
    submitted = client.post('/api/submit_demographics', json=demographics_payload)
    assert submitted.status_code == 200, submitted.get_json()

    last = None
    for index in range(12):
        pair = client.get(f'/api/get_image_pair/{index}')
        if pair.status_code != 200:
            break
        last = client.post('/api/submit_survey', json={
            'image_pair_id': pair.get_json()['id'], 'responses': answers_for_study(),
            'time_spent': 12}).get_json()
    return last


def test_a_study_with_no_email_field_finishes(tmp_path, monkeypatch):
    client = study_client(tmp_path, monkeypatch, SELECT_FIELD)

    last = run_study(client, {'occupation': 'engineer'})

    assert last is not None, 'the study served no trials at all'
    assert last.get('completed') is True, (
        f'a no-email study never reports finished, so the participant loops: {last}')


def test_a_finished_no_email_study_shows_the_thank_you_page(tmp_path, monkeypatch):
    client = study_client(tmp_path, monkeypatch, SELECT_FIELD)
    run_study(client, {'occupation': 'engineer'})

    page = client.get('/').get_data(as_text=True)

    assert 'thank-you-box' in page, 'a finished participant is back at the survey'


def test_a_no_email_study_does_not_reserve_an_answered_trial(tmp_path, monkeypatch):
    client = study_client(tmp_path, monkeypatch, SELECT_FIELD)
    run_study(client, {'occupation': 'engineer'})

    client.get('/')
    again = client.get('/api/get_image_pair/0')

    assert again.status_code == 404, (
        f'the app re-served a finished participant a trial they answered: {again.get_json()}')


def test_an_intake_posted_without_the_email_still_finishes(tmp_path, monkeypatch):
    """A study whose email field is optional: a session that posts none still owns its answers."""
    client = study_client(tmp_path, monkeypatch, SELECT_FIELD + EMAIL_OPTIONAL)
    last = run_study(client, {'occupation': 'engineer'})

    assert last is not None
    assert last.get('completed') is True, (
        f'an intake with no email leaves the participant looping: {last}')
