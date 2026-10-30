"""Audit F7: the study is indexed at boot, and a pair's row is parsed when it is served.

Serving from a study of N pairs used to mean N dicts resident in every worker process, plus a linear
scan of that list on every pair request. Both are the same root: the file was materialised because
the code had no way to reach one row.
"""
from src.survey import app as app_module


def test_a_served_row_is_the_row_the_file_at_that_position_contains():
    """A byte range has to yield the row it points at, so a served row is checked against its own TSV line."""
    store = app_module.IMAGE_PAIRS
    lines = [line for line in open(store.path, encoding='utf-8').read().splitlines()
             if line and not line.startswith('#')]
    checked = 0
    for trial_id in (store.ids[0], store.ids[len(store.ids) // 2], store.ids[-1]):
        parts = lines[trial_id - store.ids[0]].split('\t')
        row = store.get(trial_id)
        for index, column in enumerate(store.columns):
            if parts[index].strip():
                assert row[column] == parts[index], f'{column} at trial {trial_id}'
                checked += 1
    assert checked >= 3


def test_the_tutorial_pair_is_one_row_read_through_the_store():
    """Audit #11: the tutorial is a one-row study, so it must cost what one study row costs, not a parsed file per worker."""
    store = app_module.TrialStore(app_module.TUTORIAL_PAIRS_FILE, start_id=0)

    assert app_module.TUTORIAL_PAIR == store.first()
    assert app_module.TUTORIAL_PAIR['id'] == 0
    assert not hasattr(app_module, '_load_trials_from_file')


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


def test_the_row_cache_is_bounded_by_the_documented_size():
    """The bound lives on the decorator now, so the hand-rolled eviction cannot come back unnoticed."""
    assert app_module._read_trial_row.cache_info().maxsize == app_module.ROW_CACHE_SIZE

    for _ in range(3):
        for trial_id in app_module.IMAGE_PAIRS.ids:
            app_module.IMAGE_PAIRS.get(trial_id)

    info = app_module._read_trial_row.cache_info()
    assert info.currsize <= app_module.ROW_CACHE_SIZE
    assert info.hits >= len(app_module.IMAGE_PAIRS.ids) * 2, 'a repeat lookup must come from the cache'
