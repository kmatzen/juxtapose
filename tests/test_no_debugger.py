"""Audit F1: DEV_MODE is the dev-behaviour flag, not a licence to expose the Werkzeug debugger.

debug=True on Flask's built-in server serves an interactive console to anyone who reaches the port,
so the flag a developer sets to test autofill must never reach app.run.
"""
import runpy

from flask import Flask


def _start_app(monkeypatch):
    calls = []
    monkeypatch.setattr(Flask, 'run', lambda self, **kw: calls.append(kw))
    # Read flags off the returned namespace: sys.modules holds the copy conftest imported, not this fresh run.
    namespace = runpy.run_module('src.survey.app', run_name='__main__')
    return calls, namespace


def test_dev_mode_does_not_start_the_debugger(monkeypatch):
    monkeypatch.setenv('DEV_MODE', 'true')
    calls, _ = _start_app(monkeypatch)
    assert calls, 'the module never called app.run'
    assert all(call.get('debug') is False for call in calls), \
        f'app.run was started with debug={calls[0].get("debug")!r}: the debugger serves a Python console on the public port'


def test_the_dev_behaviour_flag_still_reaches_the_app(monkeypatch):
    """debug is off; the dev conveniences (autofill, referral bypass) are what DEV_MODE means."""
    monkeypatch.setenv('DEV_MODE', 'true')
    _, namespace = _start_app(monkeypatch)
    assert namespace['DEV_MODE'] is True
