"""
Tests for data logic and critical functions
"""
import pytest
from src.survey.app import get_completed_pair_ids_for_email
import os


def setup_participant_with_email(app_context, email='test@example.com', session_suffix='default'):
    """Helper to create a participant with demographics in the test database"""
    from src.survey.app import get_db
    import uuid
    
    with app_context:
        db = get_db()
        
        # Insert test participant with unique session_id
        unique_session_id = f'test-session-{uuid.uuid4()}-{session_suffix}'
        db.execute('''
            INSERT INTO participants (session_id, browser, os)
            VALUES (?, 'Chrome', 'macOS')
        ''', (unique_session_id,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Insert demographics
        db.execute('''
            INSERT INTO demographics (participant_id, email, occupation)
            VALUES (?, ?, 'Engineer')
        ''', (participant_id, email))
        
        db.commit()
        db.close()
        
        return participant_id


def test_get_completed_pair_ids_empty(client):
    """Test getting completed pairs for new user returns empty list"""
    with client.application.app_context():
        result = get_completed_pair_ids_for_email('nonexistent@example.com')
        assert result == []


def test_get_completed_pair_ids_with_prompt_question_disabled(client):
    """Test completion detection works when ENABLE_PROMPT_QUESTION=false"""
    # This tests the bug fix we made today
    from src.survey.app import get_db
    import uuid
    
    # Set up database with completed responses (no prompt fields)
    unique_email = f'test-disabled-{uuid.uuid4()}@example.com'
    participant_id = setup_participant_with_email(
        client.application.app_context(), 
        email=unique_email,
        session_suffix='disabled'
    )
    
    # Insert responses with NULL prompt fields (simulating ENABLE_PROMPT_QUESTION=false)
    with client.application.app_context():
        db = get_db()
        for pair_id in [1, 2, 3]:
            db.execute('''
                INSERT INTO survey_responses (
                    participant_id, image_pair_id,
                    better_image, image_confidence,
                    better_prompt_match, prompt_confidence,
                    better_mask_match, mask_confidence,
                    better_identity_match, identity_confidence,
                    was_randomized
                ) VALUES (?, ?, 'A', 5, NULL, NULL, 'A', 5, 'B', 4, 0)
            ''', (participant_id, pair_id))
        db.commit()
        db.close()
        
        # Should return completed pairs even though prompt fields are NULL
        result = get_completed_pair_ids_for_email(unique_email)
        assert len(result) == 3
        assert set(result) == {1, 2, 3}


def test_get_completed_pair_ids_with_prompt_question_enabled(client):
    """Test completion detection requires prompt fields when enabled"""
    # Temporarily enable prompt question
    import uuid
    original_value = os.environ.get('ENABLE_PROMPT_QUESTION')
    os.environ['ENABLE_PROMPT_QUESTION'] = 'true'
    
    # Reload app module to pick up the environment variable change
    import importlib
    from src.survey import app as app_module
    importlib.reload(app_module)
    
    try:
        # Set up participant in the reloaded app's context with unique email
        unique_email = f'test-enabled-{uuid.uuid4()}@example.com'
        participant_id = setup_participant_with_email(
            app_module.app.app_context(),
            email=unique_email,
            session_suffix='enabled'
        )
        
        with app_module.app.app_context():
            from src.survey.app import get_db
            
            # Insert response with NULL prompt fields - should NOT count as complete
            db = get_db()
            db.execute('''
                INSERT INTO survey_responses (
                    participant_id, image_pair_id,
                    better_image, image_confidence,
                    better_prompt_match, prompt_confidence,
                    better_mask_match, mask_confidence,
                    better_identity_match, identity_confidence,
                    was_randomized
                ) VALUES (?, 1, 'A', 5, NULL, NULL, 'A', 5, 'B', 4, 0)
            ''', (participant_id,))
            
            # Insert response WITH prompt fields - should count as complete
            db.execute('''
                INSERT INTO survey_responses (
                    participant_id, image_pair_id,
                    better_image, image_confidence,
                    better_prompt_match, prompt_confidence,
                    better_mask_match, mask_confidence,
                    better_identity_match, identity_confidence,
                    was_randomized
                ) VALUES (?, 2, 'B', 4, 'A', 3, 'A', 5, 'B', 4, 1)
            ''', (participant_id,))
            
            db.commit()
            db.close()
            
            # Should only return pair 2 (with prompt fields filled)
            result = app_module.get_completed_pair_ids_for_email(unique_email)
            assert len(result) == 1
            assert result[0] == 2
    finally:
        # Restore original value
        if original_value is not None:
            os.environ['ENABLE_PROMPT_QUESTION'] = original_value
        else:
            os.environ.pop('ENABLE_PROMPT_QUESTION', None)
        
        # Reload app module again to restore
        importlib.reload(app_module)


def test_multiple_participants_same_email(client):
    """Test that completed pairs are tracked across multiple sessions for same email"""
    from src.survey.app import get_db
    import uuid
    
    # Use unique email to avoid conflicts with other tests
    unique_email = f'shared-{uuid.uuid4()}@example.com'
    
    # Create first participant
    participant_id_1 = setup_participant_with_email(
        client.application.app_context(), 
        unique_email,
        session_suffix='first'
    )
    
    with client.application.app_context():
        # Add a second participant with same email
        db = get_db()
        db.execute('''
            INSERT INTO participants (session_id, browser, os)
            VALUES (?, 'Firefox', 'Windows')
        ''', (f'test-session-{uuid.uuid4()}-second',))
        participant_id_2 = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db.execute('''
            INSERT INTO demographics (participant_id, email, occupation)
            VALUES (?, ?, 'Designer')
        ''', (participant_id_2, unique_email))
        
        # Add responses for both participants
        # First participant - pair 3
        db.execute('''
            INSERT INTO survey_responses (
                participant_id, image_pair_id,
                better_image, image_confidence,
                better_mask_match, mask_confidence,
                better_identity_match, identity_confidence,
                was_randomized
            ) VALUES (?, 3, 'A', 4, 'A', 3, 'B', 5, 0)
        ''', (participant_id_1,))
        
        # Second participant - pair 5
        db.execute('''
            INSERT INTO survey_responses (
                participant_id, image_pair_id,
                better_image, image_confidence,
                better_mask_match, mask_confidence,
                better_identity_match, identity_confidence,
                was_randomized
            ) VALUES (?, 5, 'B', 3, 'A', 4, 'A', 5, 1)
        ''', (participant_id_2,))
        
        db.commit()
        db.close()
        
        # Should find responses from both participants
        result = get_completed_pair_ids_for_email(unique_email)
        assert 3 in result
        assert 5 in result
        assert len(result) == 2

