"""
Database migration script for survey application.
Handles migration from old hardcoded schema to new JSON-based schema.
"""
import sqlite3
import os
import json
import logging

logger = logging.getLogger(__name__)


def migrate_database():
    """Run database migrations."""
    # Check both possible database locations
    db_path = '/data/survey.db' if os.path.exists('/data') else 'survey.db'

    if not os.path.exists(db_path):
        logger.info("No existing database found, skipping migration (will be created fresh)")
        return

    logger.info("Checking database schema...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        _migrate_demographics(conn, cursor)
        _migrate_survey_responses(conn, cursor)
        conn.commit()
        logger.info("Database migration check completed")
    except Exception as e:
        logger.error("Migration failed: %s", e)
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_columns(cursor, table):
    """Return set of column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {col[1] for col in cursor.fetchall()}


def _migrate_demographics(conn, cursor):
    """Migrate demographics table from specific columns to JSON 'data' column."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demographics'")
    if not cursor.fetchone():
        return

    columns = _get_columns(cursor, 'demographics')

    # New schema has: id, participant_id, email, data, created_at
    # Old schema has: id, participant_id, email, occupation, has_used_image_gen, ...
    if 'data' in columns:
        logger.info("demographics table already uses JSON schema")
        return

    if 'occupation' not in columns:
        # Neither old nor new schema — skip
        return

    logger.info("Migrating demographics to JSON schema...")

    # Old demographic columns (excluding id, participant_id, email, created_at)
    old_demo_cols = [
        'occupation', 'has_used_image_gen', 'image_gen_tools',
        'works_on_ai_development', 'ai_usage_frequency', 'works_with_graphics',
        'technical_background', 'ai_familiarity', 'other_data'
    ]

    # Read all old rows
    existing_cols = columns
    select_cols = [c for c in old_demo_cols if c in existing_cols]

    rows = cursor.execute(f'''
        SELECT id, participant_id, email, created_at,
               {', '.join(select_cols)}
        FROM demographics
    ''').fetchall()

    # Create new table
    cursor.execute('''
        CREATE TABLE demographics_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            email TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')

    # Migrate rows
    for row in rows:
        row = dict(row)
        demo_data = {'email': row.get('email', '')}
        for col in select_cols:
            demo_data[col] = row.get(col, '')

        cursor.execute('''
            INSERT INTO demographics_new (id, participant_id, email, data, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (row['id'], row['participant_id'], row.get('email'),
              json.dumps(demo_data), row.get('created_at')))

    # Swap tables
    cursor.execute('DROP TABLE demographics')
    cursor.execute('ALTER TABLE demographics_new RENAME TO demographics')
    logger.info("Migrated %d demographics rows to JSON schema", len(rows))


def _migrate_survey_responses(conn, cursor):
    """Migrate survey_responses from specific columns to JSON schema."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='survey_responses'")
    if not cursor.fetchone():
        return

    columns = _get_columns(cursor, 'survey_responses')

    # New schema has: id, participant_id, image_pair_id, stimulus_data, responses,
    #                 was_randomized, time_spent, created_at
    # Old schema has: id, participant_id, image_pair_id, prompt, method_a, method_b,
    #                 image_a_url, image_b_url, identity_urls, mask_url,
    #                 better_image, image_confidence, ..., was_randomized, time_spent, created_at
    if 'stimulus_data' in columns:
        logger.info("survey_responses table already uses JSON schema")
        return

    if 'better_image' not in columns:
        # Neither old nor new schema — skip
        return

    logger.info("Migrating survey_responses to JSON schema...")

    # Stimulus columns
    stim_cols = ['prompt', 'method_a', 'method_b', 'image_a_url', 'image_b_url',
                 'identity_urls', 'mask_url']

    # Response columns → question name mapping
    response_mapping = {
        'better_image': ('image_quality', 'choice'),
        'image_confidence': ('image_quality', 'confidence'),
        'better_prompt_match': ('prompt_adherence', 'choice'),
        'prompt_confidence': ('prompt_adherence', 'confidence'),
        'better_mask_match': ('mask_adherence', 'choice'),
        'mask_confidence': ('mask_adherence', 'confidence'),
        'better_identity_match': ('identity_preservation', 'choice'),
        'identity_confidence': ('identity_preservation', 'confidence'),
    }

    existing_cols = columns
    avail_stim = [c for c in stim_cols if c in existing_cols]
    avail_resp = {k: v for k, v in response_mapping.items() if k in existing_cols}

    # Build SELECT
    all_select = ['id', 'participant_id', 'image_pair_id', 'was_randomized',
                  'created_at']
    if 'time_spent' in existing_cols:
        all_select.append('time_spent')
    all_select.extend(avail_stim)
    all_select.extend(avail_resp.keys())

    rows = cursor.execute(f'SELECT {", ".join(all_select)} FROM survey_responses').fetchall()

    # Create new table
    cursor.execute('''
        CREATE TABLE survey_responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            image_pair_id INTEGER,
            stimulus_data TEXT,
            responses TEXT,
            was_randomized INTEGER DEFAULT 0,
            time_spent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')

    for row in rows:
        row = dict(row)

        # Build stimulus_data JSON
        stimulus = {}
        for col in avail_stim:
            stimulus[col] = row.get(col, '')

        # Build responses JSON
        responses = {}
        for old_col, (q_name, field) in avail_resp.items():
            val = row.get(old_col)
            if val is not None:
                if q_name not in responses:
                    responses[q_name] = {}
                if field == 'confidence' and val is not None:
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        pass
                responses[q_name][field] = val

        cursor.execute('''
            INSERT INTO survey_responses_new
            (id, participant_id, image_pair_id, stimulus_data, responses,
             was_randomized, time_spent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['id'], row['participant_id'], row.get('image_pair_id'),
            json.dumps(stimulus), json.dumps(responses),
            row.get('was_randomized', 0),
            row.get('time_spent'),
            row.get('created_at'),
        ))

    # Swap tables
    cursor.execute('DROP TABLE survey_responses')
    cursor.execute('ALTER TABLE survey_responses_new RENAME TO survey_responses')
    logger.info("Migrated %d survey responses to JSON schema", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("=== Database Migration Tool ===")
    migrate_database()
    logger.info("=== Migration Complete ===")
