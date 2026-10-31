"""Audit 6 F7: an answer has to be one the page could have produced.

The scale is documented (confidence 1-5, likert `scale`, one of the multiple_choice options, one of
A/B/equal), and the dashboard averages whatever arrives: a posted `confidence: 501` was accepted,
stored, and reported as `avg_confidence: 501.0` - a number the admin reads as the study's result.
"""
import pytest

from tests.conftest import _boot_app

QUESTIONS = """  - name: quality
    type: ab_preference
    label: "Which looks better?"
    confidence: true
    required: true
  - name: agreement
    type: likert
    label: "How similar?"
    scale: 4
  - name: flavour
    type: multiple_choice
    label: "Pick one"
    options:
      - value: crisp
        label: Crisp
      - value: soft
        label: Soft
  - name: why
    type: free_text
    label: "Why?"
"""

STUDY = """
survey:
  title: "Scale study"
  pairs_per_user: 2
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
""" + QUESTIONS

ROWS = ''.join(
    f'prompt {i}\tMethod-A\tMethod-B\thttps://x/{i}a.png\thttps://x/{i}b.png\t\t\n'
    for i in range(3))


@pytest.fixture
def study(tmp_path, monkeypatch):
    """A booted app and a client mid-study, so a submit has a session, a participant and a trial."""
    (tmp_path / 'survey_config.yaml').write_text(STUDY, encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(ROWS, encoding='utf-8')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    client = app.test_client()
    client.get('/')
    client.post('/api/submit_demographics', json={'occupation': 'engineer'})
    pair = client.get('/api/get_image_pair/0')
    assert pair.status_code == 200, pair.get_json()
    return app, client, pair.get_json()['id']


def post(client, trial_id, responses):
    return client.post('/api/submit_survey',
                       json={'image_pair_id': trial_id, 'responses': responses, 'time_spent': 12})


def test_an_out_of_range_confidence_is_rejected(study):
    app, client, trial_id = study

    response = post(client, trial_id, {'quality': {'choice': 'A', 'confidence': 501}})

    assert response.status_code == 400, (
        f'a confidence the page cannot offer was accepted: {response.get_json()}')


def test_a_confidence_on_the_scale_lands(study):
    app, client, trial_id = study

    response = post(client, trial_id, {'quality': {'choice': 'A', 'confidence': 5}})

    assert response.status_code == 200, response.get_json()


def test_a_choice_the_page_cannot_offer_is_rejected(study):
    app, client, trial_id = study

    response = post(client, trial_id, {'quality': {'choice': 'C', 'confidence': 3}})

    assert response.status_code == 400, (
        f'a preference for a method that was not offered was accepted: {response.get_json()}')


def test_a_likert_answer_outside_its_scale_is_rejected(study):
    app, client, trial_id = study

    over = post(client, trial_id, {'agreement': {'value': 9}})
    edge = post(client, trial_id, {'agreement': {'value': 4}})

    assert over.status_code == 400, f'likert 9 on a 1-4 scale was accepted: {over.get_json()}'
    assert edge.status_code == 200, edge.get_json()


def test_a_multiple_choice_answer_must_be_one_of_its_options(study):
    app, client, trial_id = study

    invented = post(client, trial_id, {'flavour': {'value': 'tangy'}})
    offered = post(client, trial_id, {'flavour': {'value': 'crisp'}})

    assert invented.status_code == 400, f'an option the study never defined was accepted: {invented.get_json()}'
    assert offered.status_code == 200, offered.get_json()


def test_the_reported_average_stays_on_the_scale(study):
    app, client, trial_id = study
    post(client, trial_id, {'quality': {'choice': 'A', 'confidence': 5}})
    post(client, trial_id, {'quality': {'choice': 'A', 'confidence': 501}})

    admin = app.test_client()
    with admin.session_transaction() as sess:
        sess['admin_authenticated'] = True
    stats = admin.get('/api/admin/stats').get_json()

    assert stats['avg_confidence'] == 5.0, (
        f"the dashboard reports the posted 501 as the study's result: {stats['avg_confidence']}")
