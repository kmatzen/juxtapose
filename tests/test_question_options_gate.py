"""Audit 6 F3c: a question with nothing to choose cannot be answered, so it must not boot.

A required `multiple_choice` with no `options` renders a label and zero radios, so the participant
answers every trial they are shown and the app never reports the study finished: the next pair
request 404s, `/` re-serves an answered trial, and the loop repeats. A demographics `select` or
`radio` with no options is the same widget with nothing in it.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

STUDY = """
survey:
  title: "Options study"
demographics:
{demographics}
data:
  file: pairs.tsv
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
methods:
  a: method_a
  b: method_b
inputs:
  - name: prompt
    type: text
    column: prompt
outputs:
  - name: image
    type: image
    column_a: image_a_url
    column_b: image_b_url
questions:
{questions}
"""

DEMO_OK = """  - name: email
    type: email
    label: "Email"
    required: true"""
DEMO_EMPTY_SELECT = """  - name: tools
    type: select
    label: "Tools you use"
    required: true"""
QUESTIONS_OK = """  - name: image_quality
    type: ab_preference
    label: "Which looks better?"
    required: true"""
QUESTIONS_NO_OPTIONS = """  - name: notes
    type: multiple_choice
    label: "Anything else?"
    required: true"""
QUESTIONS_WITH_OPTIONS = """  - name: notes
    type: multiple_choice
    label: "Anything else?"
    required: true
    options:
      - value: "yes"
        label: "Yes"
"""
PAIRS = "a prompt\tMethod-A\tMethod-B\thttps://x/a.png\thttps://x/b.png\t\t\n"


def boot(tmp_path, questions, demographics=DEMO_OK):
    """A real import in a fresh process: refusing a study that cannot be answered is boot behaviour."""
    (tmp_path / 'survey_config.yaml').write_text(
        STUDY.format(questions=questions, demographics=demographics), encoding='utf-8')
    (tmp_path / 'pairs.tsv').write_text(PAIRS, encoding='utf-8')
    env = dict(os.environ)
    env.pop('SURVEY_DISABLE_SESSION_GATE', None)
    env.update({'SURVEY_CONFIG': str(tmp_path / 'survey_config.yaml'),
                'IMAGE_PAIRS_FILE': str(tmp_path / 'pairs.tsv'),
                'APP_ENV': 'dev',
                'PYTHONPATH': os.pathsep.join(sys.path)})
    return subprocess.run([sys.executable, '-c', 'import src.survey.app; print("booted")'],
                          env=env, cwd=str(REPO_ROOT), capture_output=True, text=True)


def test_a_question_with_nothing_to_choose_refuses_to_boot(tmp_path):
    result = boot(tmp_path, QUESTIONS_NO_OPTIONS)

    assert result.returncode != 0, (
        'a required multiple_choice with no options booted, and the study it serves never ends')
    assert 'notes' in result.stderr, f'the refusal must name the question: {result.stderr[-300:]}'
    assert 'options' in result.stderr


def test_a_demographics_choice_field_with_no_options_refuses_to_boot(tmp_path):
    result = boot(tmp_path, QUESTIONS_OK, DEMO_EMPTY_SELECT)

    assert result.returncode != 0
    assert 'tools' in result.stderr


@pytest.mark.parametrize('questions,demographics', [
    (QUESTIONS_WITH_OPTIONS, DEMO_OK),
    (QUESTIONS_OK, DEMO_OK),
])
def test_a_study_that_can_be_answered_still_boots(tmp_path, questions, demographics):
    result = boot(tmp_path, questions, demographics)

    assert result.returncode == 0, result.stderr
    assert 'booted' in result.stdout
