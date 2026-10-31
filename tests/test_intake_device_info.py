"""The intake validates every declared field and nothing at all about `device_info`.

Measured on 156fe69: `device_info: {"screen_width": {"x": 1}}` made sqlite refuse the parameter, the
route's broad `except` answered `500 An error occurred while submitting demographics`, and **no
participant and no intake row was created** - the participant is refused with a message that says
nothing. Scalar nonsense is accepted: `browser` stored 5,000 characters and `screen_width` stored
the text `wide`, and `/api/admin/participants` prints the 5,000-character cell into the roster.
"""
import pytest
import yaml

from src.survey import app as app_module
from tests.conftest import _boot_app

COLUMNS = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url', 'mask_url',
           'identity_urls']

# The shape frontend/src/lib/device-info.ts's collectDeviceInfo() posts.
REAL_DEVICE = {'browser': 'Chrome', 'browser_version': '120.0', 'os': 'macOS',
               'screen_width': 1920, 'screen_height': 1080, 'pixel_ratio': 2, 'color_depth': 24,
               'viewport_width': 1440, 'viewport_height': 900}


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = {
        'survey': {'title': 'Device', 'pairs_per_user': 1},
        'data': {'file': 'pairs.tsv', 'columns': COLUMNS},
        'methods': {'a': 'method_a', 'b': 'method_b'},
        'inputs': [{'name': 'prompt', 'type': 'text', 'column': 'prompt'}],
        'outputs': [{'name': 'image', 'type': 'image',
                     'column_a': 'image_a_url', 'column_b': 'image_b_url'}],
        'questions': [{'name': 'quality', 'type': 'ab_preference', 'label': 'Which?'}],
        'demographics': [{'name': 'email', 'type': 'email', 'label': 'Email', 'required': True}],
    }
    (tmp_path / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    row = '\t'.join(['a prompt', 'A', 'B', 'https://x/a.png', 'https://x/b.png', '', ''])
    (tmp_path / 'pairs.tsv').write_text(row + '\n')
    monkeypatch.setenv('SURVEY_CONFIG', str(tmp_path / 'survey_config.yaml'))
    monkeypatch.setenv('IMAGE_PAIRS_FILE', str(tmp_path / 'pairs.tsv'))
    monkeypatch.setenv('REFERRAL_CODES', '')
    monkeypatch.setenv('DEV_MODE', 'false')
    app = _boot_app(tmp_path, monkeypatch, csrf_enabled=False)
    test_client = app.test_client()
    test_client.get('/')
    return test_client


def _post(client, device_info):
    payload = {'email': 'device@example.com'}
    if device_info is not None:
        payload['device_info'] = device_info
    return client.post('/api/submit_demographics', json=payload)


def _rows(client, table):
    with client.application.app_context():
        db = app_module.get_db()
        try:
            return db.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n']
        finally:
            db.close()


@pytest.mark.parametrize('value', [{'x': 1}, [1, 2], 'wide', True])
def test_a_value_that_cannot_live_in_a_number_column_is_refused(client, value):
    for key in ('screen_width', 'screen_height', 'pixel_ratio', 'color_depth',
                'viewport_width', 'viewport_height'):
        response = _post(client, {key: value})
        assert response.status_code == 400, (key, value, response.get_json())
        assert key in response.get_json()['error']


def test_a_nested_value_refuses_the_intake_without_taking_the_row_with_it(client):
    """The 500 the base answers leaves no participant, so the participant cannot retry their way in."""
    response = _post(client, {'browser': 'Chrome', 'screen_width': {'x': 1}})
    assert response.status_code == 400
    assert _rows(client, 'participants') == 0
    assert _rows(client, 'demographics') == 0


def test_an_over_long_device_string_is_refused(client):
    response = _post(client, {'browser': 'B' * 5000})
    assert response.status_code == 400
    assert 'browser' in response.get_json()['error']
    assert _rows(client, 'participants') == 0


@pytest.mark.parametrize('key', ['browser', 'browser_version', 'os'])
def test_a_non_text_descriptive_value_is_refused(client, key):
    response = _post(client, {key: {'name': 'Chrome'}})
    assert response.status_code == 400
    assert key in response.get_json()['error']


@pytest.mark.parametrize('value', ['chrome', ['Chrome'], 5])
def test_a_device_info_that_is_not_an_object_is_refused(client, value):
    response = client.post('/api/submit_demographics',
                           json={'email': 'device@example.com', 'device_info': value})
    assert response.status_code == 400
    assert 'device_info' in response.get_json()['error']


def test_the_device_the_page_posts_is_accepted(client):
    response = _post(client, REAL_DEVICE)
    assert response.status_code == 200, response.get_json()
    assert _rows(client, 'participants') == 1


def test_an_intake_with_no_device_info_is_still_accepted(client):
    assert _post(client, None).status_code == 200
    assert _rows(client, 'participants') == 1
