"""
Pytest configuration and fixtures
"""
import pytest
import tempfile
import os
from src.survey import app as app_module


@pytest.fixture
def app():
    """Create application for testing"""
    # Set environment variables BEFORE importing app
    os.environ['DEV_MODE'] = 'false'
    os.environ['REFERRAL_CODES'] = ''  # Empty referral codes
    os.environ['ENABLE_PROMPT_QUESTION'] = 'false'
    
    # Reload the app module to pick up environment variables
    import importlib
    importlib.reload(app_module)
    flask_app = app_module.app
    
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test_secret_key',
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
    })
    
    # Initialize database schema
    with flask_app.app_context():
        app_module.init_db()
    
    yield flask_app
    
    # Cleanup
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

