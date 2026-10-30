"""
Pytest configuration and fixtures
"""
import pytest
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


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create application for testing, with a database per test."""
    os.environ['DEV_MODE'] = 'false'
    os.environ['REFERRAL_CODES'] = ''

    import importlib
    importlib.reload(app_module)
    flask_app = app_module.app

    # get_db()/audit_log() read module globals, so app.config alone does not isolate.
    monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'survey.db'))
    monkeypatch.setattr(app_module, 'AUDIT_LOG_FILE', str(tmp_path / 'audit.log'))

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test_secret_key',
        'WTF_CSRF_ENABLED': False,
    })

    with flask_app.app_context():
        app_module.init_db()

    yield flask_app


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
    def make(codes):
        import importlib
        from src.survey import app as app_module
        monkeypatch.setenv('REFERRAL_CODES', codes)
        monkeypatch.setenv('DEV_MODE', 'false')
        importlib.reload(app_module)
        # The reload resets the module globals conftest isolated, so re-isolate them.
        monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'survey.db'))
        monkeypatch.setattr(app_module, 'AUDIT_LOG_FILE', str(tmp_path / 'audit.log'))
        app_module.app.config.update({
            'TESTING': True,
            'SECRET_KEY': 'test_secret_key',
            'WTF_CSRF_ENABLED': False,
        })
        with app_module.app.app_context():
            app_module.init_db()
        return app_module.app.test_client()
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
    """Sample demographics data for testing"""
    return {
        'email': 'test@example.com',
        'occupation': 'Software Engineer',
        'image_gen_tools': 'Midjourney, DALL-E',
        'works_on_ai': 'yes-research',
        'ai_usage': 'often',
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
    }


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
