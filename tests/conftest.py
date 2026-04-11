"""
Pytest configuration and fixtures
"""
import pytest
import tempfile
import os
import json
from src.survey import app as app_module


@pytest.fixture
def app():
    """Create application for testing"""
    os.environ['DEV_MODE'] = 'false'
    os.environ['REFERRAL_CODES'] = ''

    import importlib
    importlib.reload(app_module)
    flask_app = app_module.app

    db_fd, db_path = tempfile.mkstemp()

    flask_app.config.update({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test_secret_key',
        'WTF_CSRF_ENABLED': False,
    })

    with flask_app.app_context():
        app_module.init_db()

    yield flask_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner"""
    return app.test_cli_runner()


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
