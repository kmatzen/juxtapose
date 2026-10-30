"""Audit 6 F6: a depends_on question is only exempt when the input it waits for is blank.

The page shows a `depends_on` question when the named input has a value for that trial
(`isSectionVisible`), and the form makes a visible required question answerable-to-submit. The
server's completeness rule asked only "does this question have an answer, and does it have
`depends_on`?" - so a follow-up the participant was SHOWN and skipped still counted as a finished
trial: the admin's completion count and the resume/thank-you gate both credited an empty answer.
"""
from tests.conftest import _boot_app
import pytest

QUESTIONS = """  - name: image_quality
    type: ab_preference
    label: "Which looks better?"
    confidence: true
    required: true
  - name: mask_adherence
    type: ab_preference
    label: "Which follows the mask?"
    confidence: true
    depends_on: mask
"""

# Pair 0 carries a mask, pair 1 does not: the follow-up is shown for one trial and hidden for the other.
ROWS = (
    'prompt 0\tMethod-A\tMethod-B\thttps://x/0a.png\thttps://x/0b.png\thttps://x/0-mask.png\t\n'
    'prompt 1\tMethod-A\tMethod-B\thttps://x/1a.png\thttps://x/1b.png\t\t\n'
)

STUDY = """
survey:
  title: "Mask study"
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
  - name: mask
    type: image
    column: mask_url
outputs:
  - name: image
    type: image
    column_a: image_a_url
    column_b: image_b_url
questions:
""" + QUESTIONS


def study_client(tmp_path, monkeypatch):
    (tmp_path / 'survey_config.yaml').write_text(STUDY, encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(ROWS, encoding='utf-8')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    return _boot_app(tmp_path, monkeypatch, csrf_enabled=False).test_client()


def joined_client(tmp_path, monkeypatch):
    client = study_client(tmp_path, monkeypatch)
    client.get('/')
    client.post('/api/submit_demographics', json={'occupation': 'engineer'})
    return client


def serve(client, index):
    pair = client.get(f'/api/get_image_pair/{index}')
    assert pair.status_code == 200, pair.get_json()
    return pair.get_json()


def submit(client, pair, responses):
    return client.post('/api/submit_survey', json={
        'image_pair_id': pair['id'], 'responses': responses, 'time_spent': 12}).get_json()


def has_mask(pair):
    return bool(str(pair['inputs'].get('mask') or '').strip())


def run(client, answers_for):
    """Answer this session's trials in served order; `answers_for(mask_present)` picks the answers."""
    last = None
    for index in range(2):
        pair = serve(client, index)
        last = submit(client, pair, answers_for(has_mask(pair)))
    return last


IMAGE_ONLY = {'image_quality': {'choice': 'A', 'confidence': 4}}
BOTH = {'image_quality': {'choice': 'A', 'confidence': 4},
        'mask_adherence': {'choice': 'B', 'confidence': 3}}


def test_a_shown_followup_left_blank_is_not_a_finished_trial(tmp_path, monkeypatch):
    client = joined_client(tmp_path, monkeypatch)

    last = run(client, lambda mask: IMAGE_ONLY)

    assert last.get('completed') is not True, (
        'the study ended on a trial whose mask question the participant was shown and left blank, '
        'so the admin counts it as a finished answer set'
    )
    progress = client.get('/api/check_demographics').get_json()
    assert progress['completed_pairs'] < 2, (
        f'the dashboard progress calls both trials done: {progress}')
    page = client.get('/').get_data(as_text=True)
    assert 'thank-you-box' not in page, 'the thank-you page appeared with a shown question unanswered'


def test_a_finished_trial_needs_the_followup_when_the_mask_is_there(tmp_path, monkeypatch):
    client = joined_client(tmp_path, monkeypatch)

    last = run(client, lambda mask: BOTH if mask else IMAGE_ONLY)

    assert last.get('completed') is True, (
        'answering the follow-up where it is shown, and not where it is hidden, must finish the study'
    )


def test_a_hidden_followup_does_not_block_the_trial(tmp_path, monkeypatch):
    """A trial with no mask hides the follow-up: the page never shows it, so it cannot be required."""
    client = joined_client(tmp_path, monkeypatch)

    for index in range(2):
        pair = serve(client, index)
        if has_mask(pair):
            submit(client, pair, BOTH)
            continue
        submit(client, pair, IMAGE_ONLY)
        progress = client.get('/api/check_demographics').get_json()
        assert progress['completed_pairs'] == 1, (
            f'the mask-less trial was not counted with only the always-shown question answered: {progress}')
        return
    pytest.fail('the study served no trial without a mask')
