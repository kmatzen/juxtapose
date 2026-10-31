"""Survey configuration loader.

Loads survey_config.yaml and provides validated config to the application.
"""

import os
import yaml


def load_config(path=None):
    """Load survey configuration from YAML file.

    Args:
        path: Path to config file. If None, uses SURVEY_CONFIG env var
              or defaults to survey_config.yaml in the project root.

    Returns:
        dict: Validated configuration.
    """
    if path is None:
        path = os.environ.get('SURVEY_CONFIG', None)

    if path is None:
        # Default: survey_config.yaml in project root (parent of src/)
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, 'survey_config.yaml')

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Survey config not found at {path}. "
            "Create a survey_config.yaml or set the SURVEY_CONFIG env var."
        )

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    _validate(config)
    _apply_defaults(config)
    return config


def _unique_names(names, what):
    """Names are answer keys, CSV columns and DOM ids at once, so a repeated one silently overwrites."""
    seen = set()
    for name in names:
        if name is None:
            continue
        if name in seen:
            raise ValueError(f"Duplicate {what} '{name}': a second one is silently overwritten "
                             "in the stored answers, the export columns and the page's ids")
        seen.add(name)


# The names templates/index.html and survey.ts's inputOfType() dispatch on; an unknown one renders no widget.
QUESTION_TYPES = ('ab_preference', 'likert', 'free_text', 'multiple_choice')
DEMOGRAPHICS_TYPES = ('email', 'text', 'number', 'textarea', 'select', 'radio', 'checkbox')
INPUT_TYPES = ('text', 'image', 'image_gallery')


def _known_type(what, name, value, allowed, renderer):
    if value not in allowed:
        raise ValueError(f"{what} '{name}' has type '{value}': {renderer} renders "
                         f"{'|'.join(allowed)}, and an unknown one shows nothing to answer")


def _validate(config):
    """Validate required top-level keys."""
    required = ['survey', 'data', 'methods', 'inputs', 'outputs', 'questions']
    for key in required:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    if not config.get('outputs'):
        raise ValueError("At least one output must be defined")
    if not config.get('questions'):
        raise ValueError("At least one question must be defined")

    # Validate column references exist in data.columns
    columns = set(config['data'].get('columns', []))
    if not columns:
        raise ValueError("data.columns must list at least one column")

    for inp in config.get('inputs', []):
        # A name with no column is a silent empty tile: the loader's `if col` guard used to wave it through.
        if not inp.get('column'):
            raise ValueError(f"Input '{inp.get('name')}' is missing 'column'")
        if inp['column'] not in columns:
            raise ValueError(f"Input '{inp['name']}' references unknown column '{inp['column']}'")
        _known_type('Input', inp.get('name'), inp.get('type'), INPUT_TYPES, 'the front end')

    for out in config.get('outputs', []):
        for key in ('column_a', 'column_b'):
            if not out.get(key):
                raise ValueError(f"Output '{out['name']}' is missing '{key}'")
            if out[key] not in columns:
                raise ValueError(f"Output '{out['name']}' references unknown column '{out[key]}'")

    for question in config.get('questions', []):
        # _apply_defaults reads q['type'], so a question without one stops here rather than as a KeyError.
        if not question.get('type'):
            raise ValueError(f"Question '{question.get('name')}' is missing 'type'")
        _known_type('Question', question.get('name'), question['type'], QUESTION_TYPES,
                    'the question template')
        scale = question.get('scale')
        if scale is not None and (isinstance(scale, bool) or not isinstance(scale, int) or scale < 2):
            # The template counts to it: a quoted scale is valid YAML and 500s every page render.
            raise ValueError(
                f"Question '{question.get('name')}' has scale {scale!r}: it must be a whole number "
                "of at least 2")
        # A choice widget with no choices renders nothing to answer: a required one is a study that never ends, so this is checked at boot.
        if question['type'] == 'multiple_choice' and not question.get('options'):
            raise ValueError(
                f"Question '{question.get('name')}' is a multiple_choice with no options: "
                "it renders nothing to answer")

    for field in config.get('demographics', []):
        _known_type('Demographics field', field.get('name'), field.get('type'),
                    DEMOGRAPHICS_TYPES, 'the intake form')
        if field.get('type') in ('select', 'radio', 'checkbox') and not field.get('options'):
            raise ValueError(
                f"Demographics field '{field.get('name')}' is a {field['type']} with no options: "
                "it renders nothing to answer")

    method_cols = [config['methods'].get('a'), config['methods'].get('b')]
    for col in method_cols:
        if col and col not in columns:
            raise ValueError(f"Methods reference unknown column '{col}'")

    _unique_names(config['data'].get('columns', []), 'data column')
    _unique_names([i.get('name') for i in config.get('inputs', [])], 'input name')
    _unique_names([o.get('name') for o in config.get('outputs', [])], 'output name')
    _unique_names([q.get('name') for q in config.get('questions', [])], 'question name')
    _unique_names([f.get('name') for f in config.get('demographics', [])], 'demographics field name')


def _apply_defaults(config):
    """Fill in default values for optional fields."""
    survey = config.setdefault('survey', {})
    survey.setdefault('title', 'Survey')
    survey.setdefault('description', '')
    survey.setdefault('contact_email', '')
    survey.setdefault('pairs_per_user', 30)
    survey.setdefault('dev_pairs', 3)
    survey.setdefault('privacy_policy_url', '')
    survey.setdefault('consent_text', '')

    config.setdefault('demographics', [])

    tutorial = config.setdefault('tutorial', {})
    tutorial.setdefault('enabled', True)
    tutorial.setdefault('steps', [])

    for inp in config.get('inputs', []):
        inp.setdefault('optional', False)
        inp.setdefault('description', '')

    for q in config.get('questions', []):
        q.setdefault('required', False)
        q.setdefault('confidence', False)
        q.setdefault('depends_on', None)
        q.setdefault('section_label', q.get('label', ''))
        if q['type'] == 'likert':
            q.setdefault('scale', 5)


def get_email_field(config):
    """Return the name of the email demographics field, or None."""
    for field in config.get('demographics', []):
        if field.get('type') == 'email':
            return field['name']
    return None
