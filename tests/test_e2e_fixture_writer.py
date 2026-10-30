"""Audit 6 F12: the fixture's config write must not report success for a config the app refuses.

`make_run.py` prints its run dir, and that line is the success signal the playwright harness
follows. It wrote `survey_config.yaml` and never asked the app's own loader whether what it wrote
is loadable, so a fixture config the app refuses at boot left the harness with a directory that
only fails later, inside a browser test, with a message about the app.

The app itself has no admin config-write path: config is read at import in `src/survey/config.py`,
and the one admin write (`/api/admin/delete_by_email`) checks `response.ok`. The finding as titled
is therefore cured at the only config writer in the repository.
"""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
MAKER = REPO / 'tests/e2e/fixture/make_run.py'


def _repo(tmp_path, mutate=None):
    """A repo-shaped tree the fixture reads: the real config, palette and tutorial pair, mutated."""
    repo = tmp_path / 'repo'
    (repo / 'frontend/src').mkdir(parents=True)
    (repo / 'examples').mkdir(parents=True)
    config = yaml.safe_load((REPO / 'survey_config.yaml').read_text())
    if mutate:
        mutate(config)
    (repo / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    shutil.copy(REPO / 'frontend/src/identity-colors.json', repo / 'frontend/src/identity-colors.json')
    shutil.copy(REPO / 'examples/tutorial_image_pair.txt', repo / 'examples/tutorial_image_pair.txt')
    return repo


def _run(monkeypatch, repo, out):
    """Run the fixture writer as the harness runs it: argv in, run dir out."""
    spec = importlib.util.spec_from_file_location('make_run_under_test', MAKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'REPO', repo)
    monkeypatch.setattr(sys, 'argv', ['make_run.py', str(out), '3'])
    module.main()


def test_the_written_config_is_one_the_app_accepts(tmp_path, monkeypatch):
    out = tmp_path / 'run'

    _run(monkeypatch, _repo(tmp_path), out)

    from src.survey.config import load_config
    assert load_config(str(out / 'survey_config.yaml'))['data']['file'] == 'trials.tsv'


def test_a_config_the_app_refuses_stops_at_the_writer(tmp_path, monkeypatch, capsys):
    def add_a_choice_question_with_no_options(config):
        config['questions'].append({'name': 'mood', 'type': 'multiple_choice', 'label': 'Mood'})

    out = tmp_path / 'run'

    with pytest.raises(SystemExit) as exit_info:
        _run(monkeypatch, _repo(tmp_path, add_a_choice_question_with_no_options), out)

    assert exit_info.value.code != 0, 'the writer exited successfully on a config the app refuses'
    captured = capsys.readouterr()
    assert str(out) not in captured.out, 'the success line printed for a run dir the app cannot boot'
    assert 'mood' in captured.err, f'the error must name what the app refused: {captured.err}'
