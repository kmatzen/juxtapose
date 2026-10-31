"""
Pytest configuration and fixtures
"""
import pytest
import re
import tempfile
import os
import json
os.environ.setdefault('APP_ENV', 'dev')

# Sessions in tests are hand-built and carry no version stamp, so the suite runs with the
# stale-session gate opted out by name. The gate itself is tested in test_security.py.
os.environ.setdefault('SURVEY_DISABLE_SESSION_GATE', 'true')

# Production boots in subprocess tests must name a shared rate-limit store to get past the app.py
# gate. The in-process suite stays on memory://: flask-limiter dials a redis URL on the first
# limited request, not at import, so pointing the suite at a host that does not exist fails 120 tests.
REDIS_STORE = 'redis://limiter.test:6379/0'

from src.survey import app as app_module


def _boot_app(tmp_path, monkeypatch, csrf_enabled):
    """Reload the app on this test's database, saying plainly whether CSRF is on.

    Every form in the app posts a CSRF token, and the bulk suite turns the gate off to keep its
    posts short. That left the gate with no coverage at all, which is how a form missing its token
    shipped, so `csrf_app` below keeps it on and reads the token off the rendered page.
    """
    import importlib
    importlib.reload(app_module)
    flask_app = app_module.app

    # get_db()/audit_log() read module globals, so app.config alone does not isolate.
    monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'survey.db'))
    monkeypatch.setattr(app_module, 'AUDIT_LOG_FILE', str(tmp_path / 'audit.log'))

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test_secret_key',
        'WTF_CSRF_ENABLED': csrf_enabled,
    })

    with flask_app.app_context():
        app_module.init_db()

    return flask_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create application for testing, with a database per test."""
    os.environ['DEV_MODE'] = 'false'
    os.environ['REFERRAL_CODES'] = ''

    yield _boot_app(tmp_path, monkeypatch, csrf_enabled=False)


@pytest.fixture
def csrf_app(tmp_path, monkeypatch):
    """CSRF left ON: the gate is a security behaviour, so at least one fixture must exercise it."""
    os.environ['DEV_MODE'] = 'false'
    os.environ['REFERRAL_CODES'] = ''

    yield _boot_app(tmp_path, monkeypatch, csrf_enabled=True)


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


# The two shapes the app hands a token out in: a hidden form field, and the meta tag the TS reads.
_CSRF_FIELD = re.compile(r'name="csrf_token" value="([^"]+)"')
_CSRF_META = re.compile(r'name="csrf-token" content="([^"]+)"')


def csrf_token(response, field=True):
    """Pull the CSRF token out of a rendered page, the way the browser gets it."""
    pattern = _CSRF_FIELD if field else _CSRF_META
    found = pattern.search(response.get_data(as_text=True))
    if not found:
        raise AssertionError('the rendered page carries no CSRF token to post back')
    return found.group(1)


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def referral_client(tmp_path, monkeypatch):
    """REFERRAL_CODES is read at import, so a gating test must re-import the app with it set."""
    def make(codes, csrf_enabled=False):
        monkeypatch.setenv('REFERRAL_CODES', codes)
        monkeypatch.setenv('DEV_MODE', 'false')
        return _boot_app(tmp_path, monkeypatch, csrf_enabled=csrf_enabled).test_client()
    return make


@pytest.fixture
def sample_image_pair():
    """Sample image pair data for testing"""
    return {
        'id': 1,
        'prompt': 'Test prompt',
        'method_a': 'Method A',
        'method_b': 'Method B',
        'image_a_url': 'http://example.com/a.jpg',
        'image_b_url': 'http://example.com/b.jpg',
        'identity_urls': 'http://example.com/id1.jpg,http://example.com/id2.jpg',
        'mask_url': 'http://example.com/mask.jpg'
    }


@pytest.fixture
def sample_demographics():
    """An intake the shipped study accepts: 8 fields are required."""
    return complete_intake({
        'email': 'test@example.com',
        'occupation': 'software-engineer',
        'image_gen_tools': 'midjourney, dalle',
        'works_on_ai_development': 'no',
        'ai_usage_frequency': 'often',
        'works_with_graphics': 'hobbyist',
        'ai_familiarity': 'intermediate',
        'device_info': {
            'browser': 'Chrome',
            'browser_version': '120.0',
            'os': 'macOS',
            'screen_width': 1920,
            'screen_height': 1080,
            'pixel_ratio': 2.0,
            'color_depth': 24,
            'viewport_width': 1200,
            'viewport_height': 800
        }
    })


# ---------------------------------------------------------------------------
# Test helpers for new JSON schema
# ---------------------------------------------------------------------------

def insert_demographics(db, participant_id, email, **extra):
    """Insert demographics row using new JSON schema."""
    data = {'email': email}
    data.update(extra)
    db.execute(
        'INSERT INTO demographics (participant_id, email, data) VALUES (?, ?, ?)',
        (participant_id, email, json.dumps(data))
    )


def insert_response(db, participant_id, image_pair_id, responses,
                     stimulus=None, was_randomized=0, time_spent=None):
    """Insert survey_responses row using new JSON schema.

    responses: dict like {'image_quality': {'choice': 'A', 'confidence': 4}, ...}
    stimulus: dict of stimulus data (prompt, method_a, etc.)
    """
    db.execute('''
        INSERT INTO survey_responses
        (participant_id, image_pair_id, stimulus_data, responses, was_randomized, time_spent)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        participant_id, image_pair_id,
        json.dumps(stimulus or {}),
        json.dumps(responses),
        was_randomized,
        time_spent,
    ))


# The shipped study's intake asks 8 required questions; a test that is not about the intake sends a complete one.
COMPLETE_INTAKE = {
    'email': 'tester@example.com',
    'occupation': 'designer',
    'technical_background': 'basic',
    'has_used_image_gen': 'occasionally',
    'image_gen_tools': 'none',
    'works_on_ai_development': 'no',
    'ai_usage_frequency': 'sometimes',
    'works_with_graphics': 'hobbyist',
    'ai_familiarity': 'basic',
    'consent': 'yes',
}


def complete_intake(overrides=None, **kwargs):
    intake = dict(COMPLETE_INTAKE)
    intake.update(overrides or {})
    intake.update(kwargs)
    return intake


def complete_intake_for(config, **overrides):
    """An intake that answers what this study declares, using each field's first option."""
    intake = {}
    for field in config.get('demographics', []):
        name, kind = field['name'], field.get('type')
        options = [o.get('value') for o in field.get('options', [])]
        if kind == 'email':
            intake[name] = 'tester@example.com'
        elif options:
            intake[name] = options[0] if kind != 'checkbox' else ', '.join(options[:2])
        else:
            intake[name] = 'tester'
    intake.update(overrides)
    return intake
