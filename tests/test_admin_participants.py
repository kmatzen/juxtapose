"""Audit 6 F9: the dashboard cannot answer "who joined, and how far did each get".

The only grouped view was the browser grouping the responses page it had loaded. That page is
paged by *response*, so a participant's answers split across pages: on the audit's 30-participant
study the Demographics view listed 14 participants and gave the last one 5 of 15 answers, and the
analyst read that as the cohort and as a dropout at trial 5.
"""
import json

import pytest

from tests.conftest import _boot_app

PAIRS = 25
PAIRS_PER_USER = 20

STUDY = f"""
survey:
  title: "Roster study"
  pairs_per_user: {PAIRS_PER_USER}
demographics:
  - name: occupation
    type: select
    label: "Occupation"
    required: true
    options:
      - value: engineer
        label: Engineer
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
  - name: image_quality
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

ROWS = ''.join(
    f'prompt {i}\tMethod-A\tMethod-B\thttps://x/{i}a.png\thttps://x/{i}b.png\t\t\n'
    for i in range(PAIRS))

ANSWERS = {'image_quality': {'choice': 'A', 'confidence': 4},
           'prompt_adherence': {'choice': 'B', 'confidence': 3}}

# The audit's cohort: 14 finished the 20-trial study, 5 stopped at trial 15, 11 stopped earlier.
COHORT = ([('finished', 20)] * 14
          + [('at-fifteen', 15)] * 5
          + [('early', 1 + (i % 9)) for i in range(11)])


@pytest.fixture
def roster(tmp_path, monkeypatch):
    """A booted study whose database holds the audit's 30-participant cohort, and an admin client."""
    from src.survey.app import get_db

    (tmp_path / 'survey_config.yaml').write_text(STUDY, encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(ROWS, encoding='utf-8')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)

    with app.app_context():
        db = get_db()
        for index, (_kind, answered) in enumerate(COHORT):
            cursor = db.execute('INSERT INTO participants (session_id, browser, os) VALUES (?, ?, ?)',
                                (f'roster-{index}', 'Chrome', 'macOS'))
            participant_id = cursor.lastrowid
            db.execute('INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
                       (participant_id, f'p{index}@lab.example',
                        json.dumps({'email': f'p{index}@lab.example', 'occupation': 'engineer'})))
            for pair_id in range(1, answered + 1):
                db.execute('INSERT INTO survey_responses '
                           '(participant_id, image_pair_id, stimulus_data, responses, time_spent) '
                           'VALUES (?, ?, ?, ?, 12)',
                           (participant_id, pair_id, json.dumps({'inputs': {'prompt': 'p'}}),
                            json.dumps(ANSWERS)))
        db.commit()
        db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    return client


def test_the_roster_counts_every_participant_not_just_the_ones_in_the_response_page(roster):
    page = roster.get('/api/admin/participants?limit=200').get_json()

    assert page['total'] == 30, f'the roster lost participants: {page["total"]}'
    assert len(page['rows']) == 30, 'the roster is capped by a response-sized page'
    assert sorted(row['trials_completed'] for row in page['rows']) == sorted(
        count for _kind, count in COHORT), 'a participant was counted with only part of their answers'


def test_the_roster_reports_the_study_completion_and_where_people_stop(roster):
    summary = roster.get('/api/admin/participants').get_json()['summary']

    assert summary['started'] == 30
    assert summary['completed'] == 14, (
        f'14 of 30 finished the {PAIRS_PER_USER}-trial study; the roster reports {summary["completed"]}')
    assert summary['dropout'].get('15') == 5, (
        f'5 people stopped at trial 15; the roster reports {summary["dropout"]}')


def test_the_roster_pages_by_participant_not_by_response(roster):
    page = roster.get('/api/admin/participants?limit=10&offset=0').get_json()

    assert len(page['rows']) == 10
    assert page['total'] == 30
    assert all(row['trials_completed'] > 0 for row in page['rows']), (
        'a participant on the page boundary arrived with a truncated count')
    assert page['rows'][0]['email'].startswith('p')


def test_the_roster_is_for_admins_only(roster):
    anon = roster.application.test_client()

    response = anon.get('/api/admin/participants')

    assert response.status_code == 302, 'the roster of participants is not admin-only'
