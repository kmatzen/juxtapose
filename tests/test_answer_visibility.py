"""A `depends_on` answer is refused for a trial that never showed the question.

Measured on 156fe69: on a trial whose mask input is blank the page does not render `mask_quality`,
and posting `{"mask_quality": {"value": 5}}` returned 200, was stored, and the CSV column
`mask_quality_value` read `5`. The dashboard's averages count that row, so a scripted client can
plant a judgement no participant made in a column the researcher trusts. The app already knows the
rule - `_question_shown` is what the completeness check asks.
"""
import pytest
import yaml

from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']


def _row(mask):
    return '\t'.join(['a prompt', 'A', 'B', 'https://x/a.png', 'https://x/b.png', mask, ''])


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Visibility', 'pairs_per_user': 2},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'},
                   {'name': 'mask', 'type': 'image', 'column': 'mask_url', 'optional': True}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?',
                       'confidence': True},
                      {'name': 'mask_quality', 'type': 'likert', 'label': 'Mask', 'scale': 5,
                       'depends_on': 'mask'}],
        'demographics': [{'name': 'email', 'type': 'email', 'label': 'Email', 'required': True}],
    }
    (tmp_path / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    (tmp_path / 'pairs.tsv').write_text(_row('') + '\n' + _row('https://x/m.png') + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    test_client = app.test_client()
    test_client.get('/')
    posted = test_client.post('/api/submit_demographics', json={'email': 'seen@example.com',
                                                                'consent': 'yes'})
    assert posted.status_code == 200, posted.get_json()
    return test_client


def _post_answer(client, served, mask_quality=None):
    responses = {'quality': {'choice': 'A', 'confidence': 4}}
    if mask_quality is not None:
        responses['mask_quality'] = {'value': mask_quality}
    return client.post('/api/submit_survey', json={'image_pair_id': served['id'],
                                                   'responses': responses, 'time_spent': 12})


def _served(client, index):
    return client.get(f'/api/get_image_pair/{index}').get_json()


def _served_with(client, wants_mask):
    """The session's pair order is the study's shuffle, so pick the trial by what it carries."""
    for index in (0, 1):
        served = _served(client, index)
        if bool((served.get('mask_url') or '').strip()) == wants_mask:
            return served
    raise AssertionError(f'no served trial with wants_mask={wants_mask}')


def test_an_answer_for_a_question_the_trial_never_showed_is_refused_by_name(client):
    served = _served_with(client, wants_mask=False)
    assert served['mask_url'] is None, 'this trial carries no mask, so the page shows no such question'
    response = _post_answer(client, served, mask_quality=5)
    assert response.status_code == 400, response.get_json()
    assert 'mask_quality' in response.get_json()['error']


def test_the_answer_the_page_could_have_given_is_still_accepted(client):
    """Both halves of the pair list: a trial with a mask accepts the follow-up, one without refuses it."""
    outcomes = []
    for index in (0, 1):
        served = _served(client, index)
        shown = bool((served.get('mask_url') or '').strip())
        response = _post_answer(client, served, mask_quality=4)
        outcomes.append((shown, response.status_code))
    assert (True, 200) in outcomes, outcomes
    assert (False, 400) in outcomes, outcomes


def test_a_question_that_is_always_shown_is_unaffected(client):
    served = _served(client, 0)
    assert _post_answer(client, served).status_code == 200


def test_the_refused_answer_leaves_nothing_in_the_export(client):
    served = _served_with(client, wants_mask=False)
    assert _post_answer(client, served, mask_quality=5).status_code == 400
    _post_answer(client, served)
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    lines = client.get('/api/admin/export').get_data(as_text=True).splitlines()
    column = lines[0].split(',').index('mask_quality_value')
    assert [line.split(',')[column] for line in lines[1:]] == ['']
