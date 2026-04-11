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


def _validate(config):
    """Validate required top-level keys."""
    required = ['survey', 'data', 'methods', 'inputs', 'outputs', 'questions', 'layout']
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
        col = inp.get('column')
        if col and col not in columns:
            raise ValueError(f"Input '{inp['name']}' references unknown column '{col}'")

    for out in config.get('outputs', []):
        for key in ('column_a', 'column_b'):
            col = out.get(key)
            if col and col not in columns:
                raise ValueError(f"Output '{out['name']}' references unknown column '{col}'")

    method_cols = [config['methods'].get('a'), config['methods'].get('b')]
    for col in method_cols:
        if col and col not in columns:
            raise ValueError(f"Methods reference unknown column '{col}'")


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

    for inp in config.get('inputs', []):
        inp.setdefault('optional', False)
        inp.setdefault('interactions', [])
        inp.setdefault('description', '')

    for out in config.get('outputs', []):
        out.setdefault('interactions', [])

    for q in config.get('questions', []):
        q.setdefault('required', False)
        q.setdefault('confidence', False)
        q.setdefault('depends_on', None)
        q.setdefault('section_label', q.get('label', ''))
        if q['type'] == 'likert':
            q.setdefault('scale', 5)

    for col in config['layout'].get('columns', []):
        col.setdefault('sticky', False)
        col.setdefault('width', 'auto')
        for section in col.get('sections', []):
            section.setdefault('direction', 'column')
            section.setdefault('label', '')
            section.setdefault('widgets', [])


def get_email_field(config):
    """Return the name of the email demographics field, or None."""
    for field in config.get('demographics', []):
        if field.get('type') == 'email':
            return field['name']
    return None


def build_column_map(config):
    """Build a mapping from column names to their index in data.columns."""
    return {col: i for i, col in enumerate(config['data']['columns'])}


def get_inputs_by_name(config):
    """Return dict of input configs keyed by name."""
    return {inp['name']: inp for inp in config.get('inputs', [])}


def get_outputs_by_name(config):
    """Return dict of output configs keyed by name."""
    return {out['name']: out for out in config.get('outputs', [])}


def get_questions_by_name(config):
    """Return dict of question configs keyed by name."""
    return {q['name']: q for q in config.get('questions', [])}
