"""Audit F6: the study config is parsed once, at import — serving a pair must not go hunting for it.

The audit that opened this task claimed every pair request re-read and re-parsed study_config.yaml.
It does not: _trial_count() reads SURVEY, which is the CONFIG that load_config() built at import
(app.py:102), and this repo has no meta.json at all. The finding was false, read off a stale memory
of an earlier codebase rather than off these lines.

What is worth keeping is the guarantee, so the next person can reintroduce the read in a diff that
looks innocent: a pair request opens no config file.
"""
import builtins

PAIR_REQUESTS = ('/api/get_image_pair/0', '/api/get_image_pair/1')
CONFIG_FILES = ('survey_config.yaml', 'study_config.yaml')


def test_serving_pairs_opens_no_config_file(client, monkeypatch):
    opened = []
    real_open = builtins.open

    def recording_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', recording_open)
    for url in PAIR_REQUESTS:
        assert client.get(url).status_code in (200, 302), f'{url} did not serve'

    hits = [path for path in opened if path.endswith(CONFIG_FILES)]
    assert not hits, f'pair requests read config from disk: {hits}'


def test_the_config_the_app_serves_from_is_the_one_it_parsed():
    """_trial_count must answer from the parsed config, which is what the test above proves is enough."""
    from src.survey import app as app_module

    expected = min(app_module.IMAGE_PAIRS.count, app_module.SURVEY['pairs_per_user'])
    assert app_module._trial_count() == expected
