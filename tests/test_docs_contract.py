"""Audit 6 F14: the docs a newcomer follows have to match the tree and the code.

Docs rot silently and a test does not. These are the claims that were found false - a test tree
listing files the repo no longer has, an env contract missing the two variables a study cannot boot
without, and a sentence that handed the security mode back to `DATA_DIR` after audit 1 moved it to
`APP_ENV`.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_README = (ROOT / 'tests' / 'README.md').read_text(encoding='utf-8')
README = (ROOT / 'README.md').read_text(encoding='utf-8')
ARCHITECTURE = (ROOT / 'docs' / 'frontend-architecture.md').read_text(encoding='utf-8')

PATH_IN_DOC = re.compile(r'[\w{}./-]+\.(?:py|js|ts|md|html|sh|yaml|json)\b')


def _paths_in(text):
    return {token for token in PATH_IN_DOC.findall(text) if '{' not in token}


def _tree_block(text):
    """The `tests/` tree under Test Structure, which claims to be the directory's contents."""
    section = re.search(r'## Test Structure\n(.*?)(?=\n## )', text, re.S)
    assert section, 'tests/README.md documents no Test Structure tree'
    return section.group(1)


def test_every_file_the_test_tree_lists_exists():
    missing = sorted(
        path for path in _paths_in(_tree_block(TESTS_README))
        if not (ROOT / 'tests' / path).exists() and not (ROOT / path).exists()
    )
    assert not missing, f'tests/README.md lists files the repo does not have: {missing}'


def test_the_documented_env_contract_covers_what_the_app_reads():
    source = (ROOT / 'src' / 'survey' / 'app.py').read_text(encoding='utf-8')
    read_by_app = set(re.findall(r"os\.environ(?:\.get)?\(\s*['\"]([A-Z_]+)['\"]", source))
    for name in sorted(read_by_app - {'E2E_RANDOM_SEED', 'SURVEY_DISABLE_SESSION_GATE', 'PORT'}):
        assert f'`{name}`' in README, f'README documents no {name}, which the app reads'


def test_the_security_mode_is_documented_from_one_place():
    for doc in (README, TESTS_README):
        for sentence in re.split(r'(?<=[.!?])\s+', doc):
            assert not ('DATA_DIR' in sentence and 'production mode' in sentence), (
                f'`DATA_DIR` is documented as deciding the security mode: {sentence!r}')


def test_the_frontend_doc_names_where_the_study_rules_live():
    assert 'study-state.ts' in ARCHITECTURE, 'the layer table no longer names the model module'
    assert re.search(r'components? (import|depend on)[^.]*\bmodel\b', ARCHITECTURE, re.I) \
        or 'Dependencies point down' in ARCHITECTURE, \
        'the doc no longer states the direction dependencies may point'


def test_the_documented_run_command_runs_more_than_one_worker():
    """Audit 7 F7: the app's production gate justifies redis by "every gunicorn worker keeps its
    own counters", and the README's command started a single sync worker, so the reason and the
    deployment disagreed and every participant queued behind one worker."""
    command = re.search(r'^gunicorn .*$', README, re.M)
    assert command, 'README documents no gunicorn command'
    assert '--workers' in command.group(0), (
        f'the documented command runs gunicorn\'s default one sync worker: {command.group(0)!r}')


def test_the_python_dependencies_have_upper_bounds():
    """Audit 7 F8: the JS side has package-lock.json and `npm ci`; pip resolved open ranges on
    every CI run, so a Flask patch could change cookie behaviour mid-study with no recorded
    version to go back to."""
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    requirements = re.findall(r'"([A-Za-z0-9_.\[\]-]+)([<>=!~]+[^"]*)"', pyproject)
    open_ranges = [name for name, spec in requirements if ',' not in spec]
    assert not open_ranges, f'dependencies with no upper bound: {open_ranges}'
