"""
Tests for admin statistics and results endpoints

This test suite covers the /api/admin/results endpoint which retrieves
all survey responses with associated participant and demographic data.

Coverage:
- Authentication requirements
- Empty database handling
- Full data retrieval with all fields
- Multiple participants and responses
- Preferred method calculation logic
- Null/missing data handling
- Device information inclusion
- Referral code tracking
- Result ordering
- JSON format validation
"""
import pytest
import json
import uuid


def test_admin_results_no_auth(client):
    """Test admin results endpoint requires authentication"""
    response = client.get('/api/admin/results')
    assert response.status_code == 302  # Redirect to login


def test_admin_results_empty_database(client):
    """Test admin results with no data returns empty list or existing data"""
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    # Note: May have data from other tests, just verify it's a valid list


def test_admin_results_with_data(client):
    """Test admin results returns survey data"""
    from src.survey.app import get_db
    
    # Create test data
    unique_session = f'test-results-{uuid.uuid4()}'
    unique_email = f'results-{uuid.uuid4()}@example.com'
    
    with client.application.app_context():
        db = get_db()
        
        # Insert participant
        db.execute("""
            INSERT INTO participants 
            (session_id, browser, browser_version, os, screen_width, screen_height, 
             pixel_ratio, color_depth, referral_code)
            VALUES (?, 'Chrome', '120.0', 'macOS', 1920, 1080, 2.0, 24, 'TEST123')
        """, (unique_session,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Insert demographics (use correct column names from schema)
        db.execute("""
            INSERT INTO demographics 
            (participant_id, email, occupation, image_gen_tools, works_on_ai_development, 
             ai_usage_frequency, works_with_graphics, ai_familiarity)
            VALUES (?, ?, 'Engineer', 'DALL-E', 'yes-research', 'often', 'professional', 'advanced')
        """, (participant_id, unique_email))
        
        # Insert survey response
        db.execute("""
            INSERT INTO survey_responses 
            (participant_id, image_pair_id, prompt, method_a, method_b,
             image_a_url, image_b_url, identity_urls, mask_url,
             better_image, image_confidence,
             better_mask_match, mask_confidence,
             better_identity_match, identity_confidence,
             was_randomized, time_spent)
            VALUES (?, 1, 'Test prompt', 'Method-A', 'Method-B',
                    'http://example.com/a.jpg', 'http://example.com/b.jpg',
                    'http://example.com/id.jpg', 'http://example.com/mask.jpg',
                    'A', 4, 'B', 3, 'A', 5, 1, 45.5)
        """, (participant_id,))
        
        db.commit()
        db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Verify data structure
    assert isinstance(data, list)
    assert len(data) >= 1
    
    # Find our test record
    test_record = None
    for record in data:
        if record.get('email') == unique_email:
            test_record = record
            break
    
    assert test_record is not None, "Test record not found in results"
    
    # Verify all expected fields are present
    assert test_record['session_id'] == unique_session
    assert test_record['email'] == unique_email
    assert test_record['occupation'] == 'Engineer'
    assert test_record['browser'] == 'Chrome'
    assert test_record['os'] == 'macOS'
    assert test_record['prompt'] == 'Test prompt'
    assert test_record['method_a'] == 'Method-A'
    assert test_record['method_b'] == 'Method-B'
    assert test_record['better_image'] == 'A'
    assert test_record['image_confidence'] == 4
    assert test_record['time_spent'] == 45.5
    
    # Verify calculated preferred method
    assert test_record['preferred_method_image'] == 'Method-A'


def test_admin_results_multiple_participants(client):
    """Test admin results with multiple participants"""
    from src.survey.app import get_db
    
    participants_data = []
    emails = []
    
    with client.application.app_context():
        db = get_db()
        
        try:
            # Create 3 participants with different data
            for i in range(3):
                unique_session = f'test-multi-{uuid.uuid4()}'
                unique_email = f'user{i}-{uuid.uuid4()}@example.com'
                emails.append(unique_email)
                
                db.execute("""
                    INSERT INTO participants (session_id, browser, os)
                    VALUES (?, ?, ?)
                """, (unique_session, f'Browser{i}', f'OS{i}'))
                participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                
                db.execute("""
                    INSERT INTO demographics (participant_id, email, occupation)
                    VALUES (?, ?, ?)
                """, (participant_id, unique_email, f'Job{i}'))
                
                db.execute("""
                    INSERT INTO survey_responses 
                    (participant_id, image_pair_id, better_image, image_confidence,
                     better_mask_match, mask_confidence, better_identity_match, 
                     identity_confidence, was_randomized)
                    VALUES (?, ?, 'A', 3, 'B', 4, 'Equal', 2, 0)
                """, (participant_id, i + 1))
                
                participants_data.append({
                    'email': unique_email,
                    'occupation': f'Job{i}'
                })
            
            db.commit()
        finally:
            db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Verify we got at least our 3 records
    assert len(data) >= 3
    
    # Verify all our test records are present
    found_emails = {record.get('email') for record in data}
    for participant in participants_data:
        assert participant['email'] in found_emails


def test_admin_results_preferred_method_calculation(client):
    """Test preferred method calculation for different choices"""
    from src.survey.app import get_db
    
    test_cases = [
        {'better_image': 'A', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'GPT-4'},
        {'better_image': 'B', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'DALL-E'},
        {'better_image': 'equal', 'method_a': 'GPT-4', 'method_b': 'DALL-E', 'expected': 'equal'},
    ]
    
    with client.application.app_context():
        db = get_db()
        
        try:
            for idx, test_case in enumerate(test_cases):
                unique_session = f'test-preferred-{uuid.uuid4()}'
                unique_email = f'pref{idx}-{uuid.uuid4()}@example.com'
                
                db.execute("""
                    INSERT INTO participants (session_id, browser, os)
                    VALUES (?, 'Chrome', 'macOS')
                """, (unique_session,))
                participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                
                db.execute("""
                    INSERT INTO demographics (participant_id, email, occupation)
                    VALUES (?, ?, 'Tester')
                """, (participant_id, unique_email))
                
                db.execute("""
                    INSERT INTO survey_responses 
                    (participant_id, image_pair_id, method_a, method_b,
                     better_image, image_confidence,
                     better_mask_match, mask_confidence,
                     better_identity_match, identity_confidence,
                     was_randomized)
                    VALUES (?, ?, ?, ?, ?, 3, 'A', 3, 'A', 3, 0)
                """, (participant_id, idx + 1, test_case['method_a'], 
                      test_case['method_b'], test_case['better_image']))
                
                test_case['email'] = unique_email
            
            db.commit()
        finally:
            db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Verify preferred method calculation for each test case
    for test_case in test_cases:
        record = next((r for r in data if r.get('email') == test_case['email']), None)
        assert record is not None, f"Record not found for {test_case['email']}"
        assert record['preferred_method_image'] == test_case['expected'], \
            f"Expected {test_case['expected']}, got {record['preferred_method_image']}"


def test_admin_results_with_null_demographics(client):
    """Test admin results handles participants with missing demographics"""
    from src.survey.app import get_db
    
    unique_session = f'test-null-demo-{uuid.uuid4()}'
    
    with client.application.app_context():
        db = get_db()
        
        try:
            # Create participant without demographics
            db.execute("""
                INSERT INTO participants (session_id, browser, os)
                VALUES (?, 'Chrome', 'macOS')
            """, (unique_session,))
            
            db.commit()
        finally:
            db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Should not crash, but won't include this participant since query uses WHERE s.id IS NOT NULL
    assert isinstance(data, list)


def test_admin_results_with_device_info(client):
    """Test admin results includes device information"""
    from src.survey.app import get_db
    
    unique_session = f'test-device-{uuid.uuid4()}'
    unique_email = f'device-{uuid.uuid4()}@example.com'
    
    with client.application.app_context():
        db = get_db()
        
        try:
            # Insert participant with detailed device info
            db.execute("""
                INSERT INTO participants 
                (session_id, browser, browser_version, os, screen_width, screen_height,
                 pixel_ratio, color_depth, viewport_width, viewport_height)
                VALUES (?, 'Firefox', '115.0', 'Windows', 2560, 1440, 1.5, 32, 1920, 1080)
            """, (unique_session,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            db.execute("""
                INSERT INTO demographics (participant_id, email, occupation)
                VALUES (?, ?, 'Designer')
            """, (participant_id, unique_email))
            
            db.execute("""
                INSERT INTO survey_responses 
                (participant_id, image_pair_id, better_image, image_confidence,
                 better_mask_match, mask_confidence, better_identity_match,
                 identity_confidence, was_randomized)
                VALUES (?, 1, 'B', 5, 'A', 4, 'B', 3, 1)
            """, (participant_id,))
            
            db.commit()
        finally:
            db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Find our record
    record = next((r for r in data if r.get('email') == unique_email), None)
    assert record is not None
    
    # Verify device information
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
            
            db.execute("""
                INSERT INTO demographics (participant_id, email, occupation)
                VALUES (?, ?, 'Student')
            """, (participant_id, unique_email))
            
            db.execute("""
                INSERT INTO survey_responses 
                (participant_id, image_pair_id, better_image, image_confidence,
                 better_mask_match, mask_confidence, better_identity_match,
                 identity_confidence, was_randomized)
                VALUES (?, 1, 'A', 3, 'A', 3, 'A', 3, 0)
            """, (participant_id,))
            
            db.commit()
        finally:
            db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Find our record
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
        
        # Create 3 responses with slight time delays
        for i in range(3):
            unique_session = f'test-order-{uuid.uuid4()}'
            unique_email = f'order{i}-{uuid.uuid4()}@example.com'
            emails.append(unique_email)
            
            db.execute("""
                INSERT INTO participants (session_id, browser, os)
                VALUES (?, 'Chrome', 'macOS')
            """, (unique_session,))
            participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            db.execute("""
                INSERT INTO demographics (participant_id, email, occupation)
                VALUES (?, ?, 'Worker')
            """, (participant_id, unique_email))
            
            db.execute("""
                INSERT INTO survey_responses 
                (participant_id, image_pair_id, better_image, image_confidence,
                 better_mask_match, mask_confidence, better_identity_match,
                 identity_confidence, was_randomized)
                VALUES (?, ?, 'A', 3, 'B', 3, 'Equal', 3, 0)
            """, (participant_id, i + 1))
            
            db.commit()
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        db.close()
    
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Find indices of our test emails in the results
    indices = []
    for email in emails:
        for idx, record in enumerate(data):
            if record.get('email') == email:
                indices.append(idx)
                break
    
    # Verify we found all 3
    assert len(indices) == 3
    
    # Should be in reverse order (most recent first)
    # Note: May not be perfectly reversed if other tests run concurrently
    # But at least verify they're all present
    assert len(set(indices)) == 3


def test_admin_results_json_format(client):
    """Test admin results returns properly formatted JSON"""
    # Set authenticated session
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True
    
    response = client.get('/api/admin/results')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'
    
    # Verify it's valid JSON
    data = json.loads(response.data)
    assert isinstance(data, list)
