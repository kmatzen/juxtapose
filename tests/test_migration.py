"""
Tests for the old-schema -> JSON-schema database migration.

The migration is the riskiest, data-mutating code in the project, so these
tests build a database with the legacy column layout, run the migration, and
assert the resulting JSON is correct.
"""
import os
import json
import sqlite3
import importlib


def _build_old_schema_db(db_path):
    """Create a database using the pre-JSON (hardcoded-column) schema."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("INSERT INTO participants (id, session_id) VALUES (1, 'sess-1')")

    # Old demographics: dedicated columns instead of a JSON `data` column.
    cur.execute('''
        CREATE TABLE demographics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            email TEXT,
            occupation TEXT,
            has_used_image_gen TEXT,
            image_gen_tools TEXT,
            works_on_ai_development TEXT,
            ai_usage_frequency TEXT,
            works_with_graphics TEXT,
            technical_background TEXT,
            ai_familiarity TEXT,
            other_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        INSERT INTO demographics
        (id, participant_id, email, occupation, ai_familiarity)
        VALUES (1, 1, 'user@example.com', 'researcher', 'expert')
    ''')

    # Old survey_responses: dedicated stimulus + response columns.
    cur.execute('''
        CREATE TABLE survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            image_pair_id INTEGER,
            prompt TEXT,
            method_a TEXT,
            method_b TEXT,
            image_a_url TEXT,
            image_b_url TEXT,
            identity_urls TEXT,
            mask_url TEXT,
            better_image TEXT,
            image_confidence INTEGER,
            better_prompt_match TEXT,
            prompt_confidence INTEGER,
            was_randomized INTEGER DEFAULT 0,
            time_spent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        INSERT INTO survey_responses
        (id, participant_id, image_pair_id, prompt, method_a, method_b,
         image_a_url, image_b_url, better_image, image_confidence,
         better_prompt_match, prompt_confidence, was_randomized, time_spent)
        VALUES (1, 1, 7, 'a cat', 'Model-A', 'Model-B',
                'http://x/a.jpg', 'http://x/b.jpg', 'A', 4,
                'B', 2, 1, 12.5)
    ''')

    conn.commit()
    conn.close()


def test_migration_converts_old_schema(tmp_path, monkeypatch):
    """Old columns are migrated into JSON `data`/`stimulus_data`/`responses`."""
    data_dir = tmp_path
    db_path = os.path.join(data_dir, 'survey.db')
    _build_old_schema_db(db_path)

    monkeypatch.setenv('DATA_DIR', str(data_dir))

    from src.survey import migrate_db
    importlib.reload(migrate_db)
    migrate_db.migrate_database()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Demographics migrated to JSON schema.
    demo_cols = {c[1] for c in cur.execute('PRAGMA table_info(demographics)')}
    assert 'data' in demo_cols
    assert 'occupation' not in demo_cols

    demo = cur.execute('SELECT * FROM demographics WHERE id = 1').fetchone()
    assert demo['email'] == 'user@example.com'
    demo_data = json.loads(demo['data'])
    assert demo_data['occupation'] == 'researcher'
    assert demo_data['ai_familiarity'] == 'expert'

    # Survey responses migrated to JSON schema.
    resp_cols = {c[1] for c in cur.execute('PRAGMA table_info(survey_responses)')}
    assert 'stimulus_data' in resp_cols
    assert 'better_image' not in resp_cols

    row = cur.execute('SELECT * FROM survey_responses WHERE id = 1').fetchone()
    stim = json.loads(row['stimulus_data'])
    assert stim['prompt'] == 'a cat'
    assert stim['method_a'] == 'Model-A'

    responses = json.loads(row['responses'])
    assert responses['image_quality'] == {'choice': 'A', 'confidence': 4}
    assert responses['prompt_adherence'] == {'choice': 'B', 'confidence': 2}
    assert row['was_randomized'] == 1
    assert row['time_spent'] == 12.5

    conn.close()


def test_migration_is_idempotent(tmp_path, monkeypatch):
    """Running the migration twice on an already-migrated DB is a no-op."""
    data_dir = tmp_path
    db_path = os.path.join(data_dir, 'survey.db')
    _build_old_schema_db(db_path)
    monkeypatch.setenv('DATA_DIR', str(data_dir))

    from src.survey import migrate_db
    importlib.reload(migrate_db)
    migrate_db.migrate_database()
    # Second run should not raise and should leave the JSON schema intact.
    migrate_db.migrate_database()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = {c[1] for c in conn.execute('PRAGMA table_info(survey_responses)')}
    assert 'stimulus_data' in cols
    conn.close()
