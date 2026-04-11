"""
Tests for data logic and critical functions
"""
import pytest
import json
from src.survey.app import _get_completed_trial_ids_for_email
from tests.conftest import insert_demographics, insert_response
import os


def setup_participant_with_email(app_context, email='test@example.com', session_suffix='default'):
    """Helper to create a participant with demographics in the test database"""
    from src.survey.app import get_db
    import uuid

    with app_context:
        db = get_db()
        unique_session_id = f'test-session-{uuid.uuid4()}-{session_suffix}'
        db.execute('''
            INSERT INTO participants (session_id, browser, os)
            VALUES (?, 'Chrome', 'macOS')
        ''', (unique_session_id,))
        participant_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id, email, occupation='Engineer')
        db.commit()
        db.close()
        return participant_id


def _make_responses():
    """Build a complete responses dict for testing (all required questions)."""
    return {
        'image_quality': {'choice': 'A', 'confidence': 5},
        'prompt_adherence': {'choice': 'B', 'confidence': 3},
        'mask_adherence': {'choice': 'A', 'confidence': 5},
        'identity_preservation': {'choice': 'B', 'confidence': 4},
    }


def test_get_completed_pair_ids_empty(client):
    """Test getting completed pairs for new user returns empty list"""
    with client.application.app_context():
        result = _get_completed_trial_ids_for_email('nonexistent@example.com')
        assert result == []


def test_get_completed_pair_ids_with_responses(client):
    """Test completion detection works with JSON responses"""
    from src.survey.app import get_db
    import uuid

    unique_email = f'test-complete-{uuid.uuid4()}@example.com'
    participant_id = setup_participant_with_email(
        client.application.app_context(),
        email=unique_email,
        session_suffix='complete'
    )

    with client.application.app_context():
        db = get_db()
        for pair_id in [1, 2, 3]:
            insert_response(db, participant_id, pair_id, _make_responses())
        db.commit()
        db.close()

        result = _get_completed_trial_ids_for_email(unique_email)
        assert len(result) == 3
        assert set(result) == {1, 2, 3}


def test_get_completed_pair_ids_incomplete_responses(client):
    """Test that incomplete responses are not counted"""
    from src.survey.app import get_db
    import uuid

    unique_email = f'test-incomplete-{uuid.uuid4()}@example.com'
    participant_id = setup_participant_with_email(
        client.application.app_context(),
        email=unique_email,
        session_suffix='incomplete'
    )

    with client.application.app_context():
        db = get_db()
        # Insert response missing required question (image_quality has no choice)
        insert_response(db, participant_id, 1, {
            'image_quality': {'choice': None, 'confidence': None},
            'mask_adherence': {'choice': 'A', 'confidence': 3},
            'identity_preservation': {'choice': 'B', 'confidence': 4},
        })
        # Insert complete response
        insert_response(db, participant_id, 2, _make_responses())
        db.commit()
        db.close()

        result = _get_completed_trial_ids_for_email(unique_email)
        assert 2 in result


def test_multiple_participants_same_email(client):
    """Test that completed pairs are tracked across multiple sessions for same email"""
    from src.survey.app import get_db
    import uuid

    unique_email = f'shared-{uuid.uuid4()}@example.com'

    participant_id_1 = setup_participant_with_email(
        client.application.app_context(),
        unique_email,
        session_suffix='first'
    )

    with client.application.app_context():
        db = get_db()
        db.execute('''
            INSERT INTO participants (session_id, browser, os)
            VALUES (?, 'Firefox', 'Windows')
        ''', (f'test-session-{uuid.uuid4()}-second',))
        participant_id_2 = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        insert_demographics(db, participant_id_2, unique_email, occupation='Designer')

        insert_response(db, participant_id_1, 3, _make_responses())
        insert_response(db, participant_id_2, 5, _make_responses())
        db.commit()
        db.close()

        result = _get_completed_trial_ids_for_email(unique_email)
        assert 3 in result
        assert 5 in result
        assert len(result) == 2
