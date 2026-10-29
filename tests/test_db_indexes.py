"""Audit #20: the retake/delete and dashboard lookups must not be full scans."""
from src.survey.app import get_db, init_db


def _index_names(db, table):
    return {row['name'] for row in db.execute(f'PRAGMA index_list({table})').fetchall()}


def _plan(db, sql, *params):
    return ' '.join(row['detail'] for row in db.execute(f'EXPLAIN QUERY PLAN {sql}', params).fetchall())


def test_init_db_creates_the_lookup_indexes(tmp_path, monkeypatch):
    from src.survey import app as app_module
    db_path = str(tmp_path / 'fresh.db')
    monkeypatch.setattr(app_module, 'DATABASE', db_path)
    init_db()

    db = get_db()
    try:
        assert 'idx_demographics_email' in _index_names(db, 'demographics')
        assert 'idx_responses_participant' in _index_names(db, 'survey_responses')
    finally:
        db.close()


def test_email_lookup_uses_the_index(tmp_path, monkeypatch):
    """Retake and admin-delete find participants by email."""
    from src.survey import app as app_module
    monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'plan.db'))
    init_db()

    db = get_db()
    try:
        assert 'idx_demographics_email' in _plan(db, 'SELECT id FROM demographics WHERE email = ?', 'x@example.com')
        assert 'idx_demographics_email' in _plan(db, 'DELETE FROM demographics WHERE email = ?', 'x@example.com')
    finally:
        db.close()


def test_response_lookup_uses_the_index(tmp_path, monkeypatch):
    from src.survey import app as app_module
    monkeypatch.setattr(app_module, 'DATABASE', str(tmp_path / 'plan2.db'))
    init_db()

    db = get_db()
    try:
        assert 'idx_responses_participant' in _plan(
            db, 'SELECT id FROM survey_responses WHERE participant_id = ?', 1)
    finally:
        db.close()
