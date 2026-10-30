"""Audit F7: the study is indexed at boot, and a pair's row is parsed when it is served.

Serving from a study of N pairs used to mean N dicts resident in every worker process, plus a linear
scan of that list on every pair request. Both are the same root: the file was materialised because
the code had no way to reach one row.
"""
from src.survey import app as app_module


def test_a_served_row_is_the_row_the_eager_loader_would_have_built():
    """Byte-identical behaviour, checked against the loader that still parses the whole file."""
    store = app_module.IMAGE_PAIRS
    eager = app_module._load_trials_from_file(store.relative_path, start_id=1)
    sample = [store.ids[0], store.ids[len(store.ids) // 2], store.ids[-1]]
    for trial_id in sample:
        assert store.get(trial_id) == eager[trial_id - 1]
    assert [row['id'] for row in eager] == store.ids


def test_boot_indexes_ids_without_materialising_rows():
    """Import parses no rows; the first lookup parses exactly one."""
    import importlib

    before = app_module._ROW_PARSES
    importlib.reload(app_module)
    # The one-row tutorial is eager by design; the study itself is not. The count that used to scale
    # with the study is the one that must not.
    assert app_module._ROW_PARSES <= 1, (
        f'import parsed {app_module._ROW_PARSES} rows; a 50k-pair study costs that per worker process')

    baseline = app_module._ROW_PARSES
    first_id = app_module.IMAGE_PAIRS.ids[0]
    app_module.IMAGE_PAIRS.get(first_id)
    assert app_module._ROW_PARSES == baseline + 1
    app_module.IMAGE_PAIRS.get(first_id)
    assert app_module._ROW_PARSES == baseline + 1, 'the cache must serve a repeat lookup without re-parsing'
    assert app_module.IMAGE_PAIRS.get(999_999) is None
    assert app_module._ROW_PARSES == baseline + 1, 'a lookup of an unknown id must parse nothing'
    app_module.IMAGE_PAIRS.get(app_module.IMAGE_PAIRS.ids[1])
    assert app_module._ROW_PARSES == baseline + 2
    app_module._ROW_PARSES = before
