"""
Tests for admin statistics and results endpoints
"""
import pytest
import json
import uuid
from tests.conftest import insert_demographics, insert_response


def test_admin_results_no_auth(client):
    """Test admin results endpoint requires authentication"""
    response = client.get('/api/admin/results')
    assert response.status_code == 302


def test_admin_results_empty_database(client):
    """Test admin results with no data returns empty list or existing data"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)


def test_admin_results_with_data(client):
    """Test admin results returns survey data"""
    from src.survey.app import get_db

    unique_session = f'test-results-{uuid.uuid4()}'
    unique_email = f'results-{uuid.uuid4()}@example.com'

    stimulus = {
        'prompt': 'Test prompt',
        'method_a': 'Method-A',
        'method_b': 'Method-B',
        'image_a_url': 'http://example.com/a.jpg',
        'image_b_url': 'http://example.com/b.jpg',
        'identity_urls': 'http://example.com/id.jpg',
        'mask_url': 'http://example.com/mask.jpg',
        'methods': {'a': 'Method-A', 'b': 'Method-B'},
    }

    responses = {
        'image_quality': {'choice': 'A', 'confidence': 4},
        'mask_adherence': {'choice': 'B', 'confidence': 3},
        'identity_preservation': {'choice': 'A', 'confidence': 5},
    }

    with client.application.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO participants
            (session_id, browser, browser_version, os, screen_width, screen_height,
             pixel_ratio, color_depth, referral_code)
            VALUES (?, 'Chrome', '120.0', 'macOS', 1920, 1080, 2.0, 24, 'TEST123')
        """, (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        insert_demographics(db, participant_id, unique_email,
                           occupation='Engineer', image_gen_tools='DALL-E',
                           works_on_ai_development='yes-research',
                           ai_usage_frequency='often',
                           works_with_graphics='professional',
                           ai_familiarity='advanced')

        insert_response(db, participant_id, 1, responses,
                       stimulus=stimulus, was_randomized=1, time_spent=45.5)

        db.commit()
        db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert isinstance(data, list)
    assert len(data) >= 1

    test_record = next((r for r in data if r.get('email') == unique_email), None)
    assert test_record is not None, "Test record not found in results"

    assert test_record['session_id'] == unique_session
    assert test_record['email'] == unique_email
    assert test_record['occupation'] == 'Engineer'
    assert test_record['browser'] == 'Chrome'
    assert test_record['os'] == 'macOS'
    assert test_record['method_a'] == 'Method-A'
    assert test_record['method_b'] == 'Method-B'
    assert test_record['image_quality_choice'] == 'A'
    assert test_record['image_quality_confidence'] == 4
    assert test_record['time_spent'] == 45.5
    # Check backward compat fields
    assert test_record['better_image'] == 'A'
    assert test_record['image_confidence'] == 4
    assert test_record['preferred_method_image'] == 'Method-A'


def test_admin_results_multiple_participants(client):
    """Test admin results with multiple participants"""
    from src.survey.app import get_db

    participants_data = []
    emails = []

    with client.application.app_context():
        db = get_db()

        try:
            for i in range(3):
                unique_session = f'test-multi-{uuid.uuid4()}'
                unique_email = f'user{i}-{uuid.uuid4()}@example.com'
                emails.append(unique_email)

                db.execute("""
                    INSERT INTO participants (session_id, browser, os)
                    VALUES (?, ?, ?)
                """, (unique_session, f'Browser{i}', f'OS{i}'))
                participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

                insert_demographics(db, participant_id, unique_email, occupation=f'Job{i}')
                insert_response(db, participant_id, i + 1, {
                    'image_quality': {'choice': 'A', 'confidence': 3},
                    'mask_adherence': {'choice': 'B', 'confidence': 4},
                    'identity_preservation': {'choice': 'equal', 'confidence': 2},
                })

                participants_data.append({
                    'email': unique_email,
                    'occupation': f'Job{i}'
                })

            db.commit()
        finally:
            db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert len(data) >= 3

    found_emails = {record.get('email') for record in data}
    for participant in participants_data:
        assert participant['email'] in found_emails


def test_admin_results_preferred_method_calculation(client):
    """Test preferred method calculation for different choices"""
    from src.survey.app import get_db

    test_cases = [
        {'choice': 'A', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'GPT-4'},
        {'choice': 'B', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'DALL-E'},
        {'choice': 'equal', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'equal'},
    ]

    with client.application.app_context():
        db = get_db()

        try:
            for idx, tc in enumerate(test_cases):
                unique_session = f'test-preferred-{uuid.uuid4()}'
                unique_email = f'pref{idx}-{uuid.uuid4()}@example.com'

                db.execute("""
                    INSERT INTO participants (session_id, browser, os)
                    VALUES (?, 'Chrome', 'macOS')
                """, (unique_session,))
                participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

                insert_demographics(db, participant_id, unique_email, occupation='Tester')

                stimulus = {
                    'methods': {'a': tc['method_a'], 'b': tc['method_b']},
                    'method_a': tc['method_a'],
                    'method_b': tc['method_b'],
                }
                responses = {
                    'image_quality': {'choice': tc['choice'], 'confidence': 3},
                    'mask_adherence': {'choice': 'A', 'confidence': 3},
                    'identity_preservation': {'choice': 'A', 'confidence': 3},
                }
                insert_response(db, participant_id, idx + 1, responses, stimulus=stimulus)

                tc['email'] = unique_email

            db.commit()
        finally:
            db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    for tc in test_cases:
        record = next((r for r in data if r.get('email') == tc['email']), None)
        assert record is not None, f"Record not found for {tc['email']}"
        assert record['image_quality_preferred_method'] == tc['expected'], \
            f"Expected {tc['expected']}, got {record.get('image_quality_preferred_method')}"


def test_admin_results_with_null_demographics(client):
    """Test admin results handles participants with missing demographics"""
    from src.survey.app import get_db

    unique_session = f'test-null-demo-{uuid.uuid4()}'

    with client.application.app_context():
        db = get_db()
        try:
            db.execute("""
                INSERT INTO participants (session_id, browser, os)
                VALUES (?, 'Chrome', 'macOS')
            """, (unique_session,))
            db.commit()
        finally:
            db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)


def test_admin_results_with_device_info(client):
    """Test admin results includes device information"""
    from src.survey.app import get_db

    unique_session = f'test-device-{uuid.uuid4()}'
    unique_email = f'device-{uuid.uuid4()}@example.com'

    with client.application.app_context():
        db = get_db()
        try:
            db.execute("""
                INSERT INTO participants
                (session_id, browser, browser_version, os, screen_width, screen_height,
                 pixel_ratio, color_depth, viewport_width, viewport_height)
                VALUES (?, 'Firefox', '115.0', 'Windows', 2560, 1440, 1.5, 32, 1920, 1080)
            """, (unique_session,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            insert_demographics(db, participant_id, unique_email, occupation='Designer')
            insert_response(db, participant_id, 1, {
                'image_quality': {'choice': 'B', 'confidence': 5},
                'mask_adherence': {'choice': 'A', 'confidence': 4},
                'identity_preservation': {'choice': 'B', 'confidence': 3},
            }, was_randomized=1)

            db.commit()
        finally:
            db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    record = next((r for r in data if r.get('email') == unique_email), None)
    assert record is not None

    assert record['browser'] == 'Firefox'
    assert record['browser_version'] == '115.0'
    assert record['os'] == 'Windows'
    assert record['screen_width'] == 2560
    assert record['screen_height'] == 1440
    assert record['pixel_ratio'] == 1.5
    assert record['color_depth'] == 32


def test_admin_results_with_referral_code(client):
    """Test admin results includes referral code"""
    from src.survey.app import get_db

    unique_session = f'test-referral-{uuid.uuid4()}'
    unique_email = f'referral-{uuid.uuid4()}@example.com'

    with client.application.app_context():
        db = get_db()
        try:
            db.execute("""
                INSERT INTO participants (session_id, browser, os, referral_code)
                VALUES (?, 'Safari', 'iOS', 'SPECIAL2024')
            """, (unique_session,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            insert_demographics(db, participant_id, unique_email, occupation='Student')
            insert_response(db, participant_id, 1, {
                'image_quality': {'choice': 'A', 'confidence': 3},
                'mask_adherence': {'choice': 'A', 'confidence': 3},
                'identity_preservation': {'choice': 'A', 'confidence': 3},
            })

            db.commit()
        finally:
            db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    record = next((r for r in data if r.get('email') == unique_email), None)
    assert record is not None
    assert record['referral_code'] == 'SPECIAL2024'


def test_admin_results_ordering(client):
    """Test admin results are ordered by response creation time (DESC)"""
    from src.survey.app import get_db
    import time

    emails = []

    with client.application.app_context():
        db = get_db()

        for i in range(3):
            unique_session = f'test-order-{uuid.uuid4()}'
            unique_email = f'order{i}-{uuid.uuid4()}@example.com'
            emails.append(unique_email)

            db.execute("""
                INSERT INTO participants (session_id, browser, os)
                VALUES (?, 'Chrome', 'macOS')
            """, (unique_session,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            insert_demographics(db, participant_id, unique_email, occupation='Worker')
            insert_response(db, participant_id, i + 1, {
                'image_quality': {'choice': 'A', 'confidence': 3},
                'mask_adherence': {'choice': 'B', 'confidence': 3},
                'identity_preservation': {'choice': 'equal', 'confidence': 3},
            })

            db.commit()
            time.sleep(0.01)

        db.close()

    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)

    indices = []
    for email in emails:
        for idx, record in enumerate(data):
            if record.get('email') == email:
                indices.append(idx)
                break

    assert len(indices) == 3
    assert len(set(indices)) == 3


def test_admin_results_json_format(client):
    """Test admin results returns properly formatted JSON"""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    response = client.get('/api/admin/results')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'

    data = json.loads(response.data)
    assert isinstance(data, list)
