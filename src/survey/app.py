from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort, send_from_directory
import sqlite3
import uuid
import os
import logging
from datetime import datetime, timedelta
import json
import random
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

from src.survey.config import (
    load_config, get_email_field, get_inputs_by_name,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# The mode is stated, never inferred: it decides which security gates are on, and guessing it wrong
# used to boot a "production" study with dev secrets and no complaint.
APP_ENV = os.environ.get('APP_ENV')
if APP_ENV not in ('production', 'dev'):
    raise ValueError(f"APP_ENV must be 'production' or 'dev', got {APP_ENV!r}: it decides which security gates are on, so there is no default")
IS_PRODUCTION = APP_ENV == 'production'

# Where results live; the /data mount is the container convention.
DATA_DIR = os.environ.get('DATA_DIR', '/data' if os.path.exists('/data') else '')

# Security: Require strong SECRET_KEY in production
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ValueError("SECRET_KEY environment variable must be set in production!")
    SECRET_KEY = 'dev-secret-key-change-in-production'
app.secret_key = SECRET_KEY

# Security: Session configuration
# Only require HTTPS cookies in production
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Session timeout

# Security: CSRF Protection
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None  # Don't expire CSRF tokens
csrf = CSRFProtect(app)

# Security: Rate Limiting
def _participant_key():
    """Survey limits key on the participant, not the IP: a lab, office or conference NAT puts
    a whole cohort behind one address, and per-IP caps lock out everyone after the first."""
    return session.get('session_id') or get_remote_address()


limiter = Limiter(
    app=app,
    key_func=_participant_key,
    default_limits=["1000 per hour"],
    storage_uri="memory://",
)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change this in production
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'  # Set DEV_MODE=true for testing
if IS_PRODUCTION and DEV_MODE:
    raise ValueError("DEV_MODE must be false in production: it bypasses referral codes, shortens the study and turns on answer autofill")

# Session versioning - increment this when session structure changes
SESSION_VERSION = 3  # Incremented for config-driven schema change

# Layout Configuration: Order of tiles in the three-tile grid
# Options: 'AMB' (A, Mask, B) or 'MAB' (Mask, A, B)
TILE_LAYOUT = os.environ.get('TILE_LAYOUT', 'MAB').upper()
if TILE_LAYOUT not in ['AMB', 'MAB']:
    logger.warning("Invalid TILE_LAYOUT '%s'. Using default 'MAB'. Valid options: AMB, MAB", TILE_LAYOUT)
    TILE_LAYOUT = 'MAB'

# The dashboard lists every participant email, so the shipped default is an open door.
if ADMIN_PASSWORD == 'admin123' and IS_PRODUCTION:
    raise ValueError("ADMIN_PASSWORD environment variable must be set in production!")

# Audit log file
AUDIT_LOG_FILE = os.path.join(DATA_DIR, 'audit.log') if DATA_DIR else 'audit.log'

# Referral codes - Set valid codes via environment variable (comma-separated) or in code
# If empty, no referral code is required
REFERRAL_CODES_ENV = os.environ.get('REFERRAL_CODES', '')
REFERRAL_CODES = set(code.strip() for code in REFERRAL_CODES_ENV.split(',') if code.strip()) if REFERRAL_CODES_ENV else set()

# In dev mode, bypass referral code requirement
REQUIRE_REFERRAL = bool(REFERRAL_CODES) and not DEV_MODE

# Database location: DATA_DIR for production, local for development
DATABASE = os.path.join(DATA_DIR, 'survey.db') if DATA_DIR else 'survey.db'

# ---------------------------------------------------------------------------
# Load survey configuration
# ---------------------------------------------------------------------------
CONFIG = load_config()
SURVEY = CONFIG['survey']
INPUTS_BY_NAME = get_inputs_by_name(CONFIG)
EMAIL_FIELD = get_email_field(CONFIG)

# Derive feature flags from config (env vars override)
_has_prompt_input = any(i['name'] == 'prompt' and i['type'] == 'text' for i in CONFIG.get('inputs', []))
_has_prompt_question = any(q['name'] == 'prompt_adherence' for q in CONFIG.get('questions', []))
SHOW_PROMPT = os.environ.get('SHOW_PROMPT', str(_has_prompt_input)).lower() == 'true'
ENABLE_PROMPT_QUESTION = os.environ.get('ENABLE_PROMPT_QUESTION', str(_has_prompt_question)).lower() == 'true'

# Tutorial pairs file
TUTORIAL_PAIRS_FILE = os.environ.get('TUTORIAL_PAIRS_FILE', 'examples/tutorial_image_pair.txt')

# ---------------------------------------------------------------------------
# Load trial data from TSV (config-driven columns)
# ---------------------------------------------------------------------------

def _load_trials_from_file(file_path_relative, start_id=1):
    """Load trials from a tab-separated file using config-defined columns."""
    columns = CONFIG['data']['columns']
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(base_path, file_path_relative)

    trials = []
    trial_id = start_id

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Stripping whitespace here would delete trailing empty fields, skipping valid rows.
                line = line.rstrip('\r\n')
                if not line or line.startswith('#'):
                    continue

                parts = line.split('\t')
                if len(parts) != len(columns):
                    logger.warning("Line %d has %d fields (expected %d), skipping", line_num, len(parts), len(columns))
                    continue

                row = {}
                for i, col in enumerate(columns):
                    val = parts[i].strip()
                    # Treat empty strings as None for optional inputs
                    inp = INPUTS_BY_NAME.get(col) or next(
                        (inp for inp in CONFIG['inputs'] if inp.get('column') == col), None
                    )
                    if inp and inp.get('optional') and not val:
                        val = None
                    row[col] = val

                row['id'] = trial_id
                trials.append(row)
                trial_id += 1

        if not trials:
            raise ValueError(f"No valid trials found in {file_path_relative}")

        logger.info("Loaded %d image pairs from %s", len(trials), file_path_relative)
        return trials

    except FileNotFoundError:
        # Inventing placeholder trials here would collect real responses against fake stimuli.
        raise FileNotFoundError(
            f"Trial data file not found: {file_path} "
            f"(data.file is '{file_path_relative}'; generate one with generate_pairs.py "
            "or set IMAGE_PAIRS_FILE)"
        ) from None

    except Exception as e:
        logger.error("Error loading %s: %s", file_path_relative, e)
        raise


def load_image_pairs():
    """Load main survey image pairs."""
    data_file = os.environ.get('IMAGE_PAIRS_FILE', CONFIG['data']['file'])
    return _load_trials_from_file(data_file, start_id=1)


def load_tutorial_pair():
    """Load tutorial image pair."""
    try:
        pairs = _load_trials_from_file(TUTORIAL_PAIRS_FILE, start_id=0)
        if pairs:
            return pairs[0]
        return None
    except Exception as e:
        logger.warning("Could not load tutorial pair: %s", e)
        return IMAGE_PAIRS[0] if IMAGE_PAIRS else None


# Load image pairs on startup
IMAGE_PAIRS = load_image_pairs()
TUTORIAL_PAIR = load_tutorial_pair()

# Security: Audit logging
def audit_log(action, details, user_ip=None):
    """Log security-sensitive actions"""
    try:
        timestamp = datetime.now().isoformat()
        ip = user_ip or get_remote_address()
        session_id = session.get('session_id', 'unknown')
        admin_session = 'ADMIN' if session.get('admin_authenticated') else 'USER'

        log_entry = {
            'timestamp': timestamp,
            'ip': ip,
            'session': session_id,
            'role': admin_session,
            'action': action,
            'details': details
        }

        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')

    except Exception as e:
        # Never let audit logging break the app
        logger.error("Audit logging error: %s", e)

# Session validation: Check for stale sessions
@app.before_request
def validate_session():
    """Validate session version and clear if stale"""
    if request.path.startswith('/static/'):
        return
    if app.config.get('TESTING'):
        return
    if 'session_id' in session:
        session_version = session.get('version')
        if session_version != SESSION_VERSION:
            logger.info("Clearing stale session (version %s != %s)", session_version, SESSION_VERSION)
            session.clear()

# Security: HTTP Security Headers
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ---------------------------------------------------------------------------
# Built frontend assets
# ---------------------------------------------------------------------------
STATIC_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static_dist')


def _built_assets():
    """Files emitted by `npm run build`; empty means the app is running from source assets."""
    found = set()
    for _, _, files in os.walk(STATIC_DIST):
        found.update(files)
    return found


BUILT_ASSETS = _built_assets()


def _manifest_entries():
    """Vite manifest keyed by entry basename; an asset-only build has no TS entries."""
    # Vite writes the manifest under .vite/ since v6; the root path is the older layout.
    for relative in (os.path.join('.vite', 'manifest.json'), 'manifest.json'):
        try:
            with open(os.path.join(STATIC_DIST, relative)) as manifest:
                data = json.load(manifest)
            break
        except (OSError, ValueError):
            continue
    else:
        return {}
    return {os.path.splitext(os.path.basename(key))[0]: value.get('file')
            for key, value in data.items() if value.get('isEntry')}


BUNDLE_ENTRIES = _manifest_entries()


@app.route('/dist/<path:filename>')
def dist_asset(filename):
    return send_from_directory(STATIC_DIST, filename)


@app.template_global()
def asset(filename):
    """Prefer the built asset; falling back to static keeps a clone with no npm working."""
    if filename in BUILT_ASSETS:
        return f'/dist/{filename}'
    return url_for('static', filename=filename)


@app.template_global()
def bundle(name):
    """Hashed entry chunk, e.g. bundle('main'); None keeps an unbuilt checkout rendering."""
    entry = BUNDLE_ENTRIES.get(name)
    return f'/dist/{entry}' if entry else None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_DB_READY = False


def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Initialize the database with required tables"""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            referral_code TEXT,
            browser TEXT,
            browser_version TEXT,
            os TEXT,
            screen_width INTEGER,
            screen_height INTEGER,
            pixel_ratio REAL,
            color_depth INTEGER,
            viewport_width INTEGER,
            viewport_height INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS demographics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            email TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            image_pair_id INTEGER,
            stimulus_data TEXT,
            responses TEXT,
            was_randomized INTEGER DEFAULT 0,
            time_spent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')

    # IF NOT EXISTS, so a study database predating this gets indexed on its next boot.
    db.execute('CREATE INDEX IF NOT EXISTS idx_demographics_email ON demographics (email)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_responses_participant ON survey_responses (participant_id)')

    db.commit()
    db.close()


@app.before_request
def ensure_db():
    """Create tables on first use; importing this module must not write files."""
    global _DB_READY
    if not _DB_READY:
        init_db()
        _DB_READY = True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trial_count():
    """Number of trials a user sees."""
    max_pairs = SURVEY.get('dev_pairs', 3) if DEV_MODE else SURVEY.get('pairs_per_user', 30)
    return min(len(IMAGE_PAIRS), max_pairs)


def _assign_pairs(available_pairs, num_pairs):
    """The trials this participant takes, in order. Under E2E_RANDOM_SEED the draw comes from a
    generator keyed to the session, so an extra pair request cannot shift the assignment by consuming
    a stream draw; production keeps the module stream. Keyed per session on purpose - per-participant
    variety is the counterbalancing, unlike the A/B flip, which must not follow the session id."""
    seed = os.environ.get('E2E_RANDOM_SEED')
    rng = random.Random(f'{seed}:{session.get("session_id")}') if seed else random
    pairs = list(available_pairs)
    if len(pairs) <= num_pairs:
        rng.shuffle(pairs)
        return pairs
    return rng.sample(pairs, num_pairs)


def _randomize_pair(key):
    """Which image of a pair the participant sees as A. Under E2E_RANDOM_SEED the flip comes from the
    seed and the pair, not from a stream draw (a draw's value moves when a busy runner makes the
    client ask for a pair twice) and not from the session id (a fresh uuid4 every run). Production is
    unseeded and unchanged, so counterbalancing keeps its per-session randomness."""
    seed = os.environ.get('E2E_RANDOM_SEED')
    if seed:
        return random.Random(f'{seed}:{key}').random() < 0.5
    return random.random() < 0.5


def _build_stimulus_data(trial, randomized):
    """Build the JSON-serializable stimulus dict stored per response."""
    methods_cfg = CONFIG['methods']
    data = {
        'trial_id': trial['id'],
        'methods': {
            'a': trial.get(methods_cfg['a'], ''),
            'b': trial.get(methods_cfg['b'], ''),
        },
        'inputs': {},
        'outputs': {},
        'was_randomized': randomized,
    }

    for inp in CONFIG['inputs']:
        val = trial.get(inp['column'], '')
        data['inputs'][inp['name']] = val

    for out in CONFIG['outputs']:
        a_val = trial.get(out['column_a'], '')
        b_val = trial.get(out['column_b'], '')
        if randomized:
            a_val, b_val = b_val, a_val
        data['outputs'][out['name']] = {'a': a_val, 'b': b_val}

    if randomized:
        data['methods']['a'], data['methods']['b'] = data['methods']['b'], data['methods']['a']

    return data


def _get_session_email():
    """Email of the participant this session submitted demographics for, None before that."""
    if 'session_id' not in session:
        return None
    db = get_db()
    try:
        row = db.execute('''
            SELECT d.email
            FROM demographics d
            JOIN participants p ON d.participant_id = p.id
            WHERE p.session_id = ?
            ORDER BY d.id DESC LIMIT 1
        ''', (session['session_id'],)).fetchone()
        return row['email'] if row else None
    finally:
        db.close()


def _get_completed_trial_ids_for_email(email):
    """Get list of trial IDs fully completed by this email address."""
    if not email:
        return []

    db = get_db()
    try:
        participant_ids = db.execute('''
            SELECT p.id
            FROM participants p
            JOIN demographics d ON p.id = d.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchall()

        if not participant_ids:
            return []

        pid_list = [p['id'] for p in participant_ids]
        placeholders = ','.join('?' * len(pid_list))

        rows = db.execute(f'''
            SELECT DISTINCT image_pair_id, responses
            FROM survey_responses
            WHERE participant_id IN ({placeholders})
                AND responses IS NOT NULL
        ''', pid_list).fetchall()

        completed = []
        required_questions = [q for q in CONFIG['questions'] if q.get('required') or q['type'] == 'ab_preference']

        for row in rows:
            try:
                resp = json.loads(row['responses'])
            except (json.JSONDecodeError, TypeError):
                continue

            # Check all visible required questions have answers
            all_answered = True
            for q in required_questions:
                q_resp = resp.get(q['name'])
                if not q_resp:
                    # If question depends on an optional input, it might not be required
                    if q.get('depends_on'):
                        continue
                    all_answered = False
                    break
                if q['type'] == 'ab_preference':
                    if not q_resp.get('choice'):
                        all_answered = False
                        break
                    if q.get('confidence') and q_resp.get('confidence') is None:
                        all_answered = False
                        break

            if all_answered:
                completed.append(row['image_pair_id'])

        return completed
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    """Simple health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'pairs_loaded': len(IMAGE_PAIRS),
        'dev_mode': DEV_MODE,
        'database': DATABASE
    }), 200


def _valid_email(email):
    """True if email is a usable address string.

    The stored email is rendered in the admin dashboard and used as the key for
    data-removal deletes, so it must not be arbitrary text.
    """
    return isinstance(email, str) and '@' in email and len(email) <= 255


def check_admin_auth():
    """Check if admin is authenticated"""
    return session.get('admin_authenticated', False)


def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_admin_auth():
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    """Home page - check referral code and if user has already submitted"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['version'] = SESSION_VERSION

    if REQUIRE_REFERRAL and not session.get('referral_validated'):
        return redirect(url_for('referral'))

    force_new = request.args.get('new') == 'true'

    db = get_db()
    participant = db.execute(
        'SELECT id FROM participants WHERE session_id = ?',
        (session['session_id'],)
    ).fetchone()

    if participant:
        demo = db.execute(
            'SELECT email, data FROM demographics WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        db.close()

        if demo and demo['email']:
            completed_pair_ids = _get_completed_trial_ids_for_email(demo['email'])
            expected_pairs = _trial_count()

            if DEV_MODE:
                logger.debug("Index route check: email=%s, completed=%d, expected=%d, tutorial_complete=%s", demo["email"], len(completed_pair_ids), expected_pairs, session.get("tutorial_completed", False))

            if len(completed_pair_ids) >= expected_pairs:
                if DEV_MODE and force_new:
                    if DEV_MODE:
                        logger.debug("Showing survey (force_new)")
                    return render_template('index.html', config=CONFIG,
                                           tile_layout=TILE_LAYOUT,
                                           show_prompt=SHOW_PROMPT)
                if DEV_MODE:
                    logger.debug("Showing thank you page (survey complete)")
                return render_template('thank_you.html', already_submitted=True,
                                       dev_mode=DEV_MODE, config=CONFIG)

            tutorial_enabled = CONFIG.get('tutorial', {}).get('enabled', True)
            if tutorial_enabled and not session.get('tutorial_completed', False):
                if DEV_MODE:
                    logger.debug("Redirecting to tutorial")
                return redirect(url_for('tutorial'))
    else:
        db.close()

    return render_template('index.html', config=CONFIG,
                           tile_layout=TILE_LAYOUT,
                           show_prompt=SHOW_PROMPT)


@app.route('/referral', methods=['GET', 'POST'])
def referral():
    """Referral code entry page"""
    if not REQUIRE_REFERRAL:
        session['referral_validated'] = True
        return redirect(url_for('index'))

    if request.method == 'POST':
        code = request.form.get('referral_code', '').strip().upper()
        if code in REFERRAL_CODES:
            session['referral_validated'] = True
            session['referral_code'] = code
            return redirect(url_for('index'))
        else:
            return render_template('referral.html', config=CONFIG,
                                   error='Invalid referral code. Please check and try again.')

    return render_template('referral.html', config=CONFIG)


@app.route('/reset_session')
def reset_session():
    """Reset session - useful for dev/testing or shared computers"""
    if DEV_MODE:
        return reset_session_logic()
    else:
        return render_template('reset_session_confirm.html', config=CONFIG)


def reset_session_logic():
    """Core logic for resetting session and deleting user data"""
    email_to_delete = None
    logger.info("Reset session requested")

    if 'session_id' in session:
        logger.info("Found session_id: %s", session["session_id"])
        db = get_db()
        try:
            participant = db.execute(
                'SELECT id FROM participants WHERE session_id = ?',
                (session['session_id'],)
            ).fetchone()

            if participant:
                logger.info("Found participant: %s", participant["id"])
                demo = db.execute(
                    'SELECT email FROM demographics WHERE participant_id = ?',
                    (participant['id'],)
                ).fetchone()

                if demo:
                    email_to_delete = demo['email']
                    logger.info("Resetting session and deleting data for: %s", email_to_delete)

                    all_participants = db.execute('''
                        SELECT p.id FROM participants p
                        JOIN demographics d ON p.id = d.participant_id
                        WHERE d.email = ?
                    ''', (email_to_delete,)).fetchall()

                    participant_ids = [p['id'] for p in all_participants]

                    if participant_ids:
                        placeholders = ','.join('?' * len(participant_ids))
                        deleted_responses = db.execute(f'DELETE FROM survey_responses WHERE participant_id IN ({placeholders})', participant_ids)
                        logger.info("Deleted %d survey responses", deleted_responses.rowcount)
                        deleted_demographics = db.execute(f'DELETE FROM demographics WHERE participant_id IN ({placeholders})', participant_ids)
                        logger.info("Deleted %d demographics records", deleted_demographics.rowcount)
                        deleted_participants = db.execute(f'DELETE FROM participants WHERE id IN ({placeholders})', participant_ids)
                        logger.info("Deleted %d participant records", deleted_participants.rowcount)
                        db.commit()
                        logger.info("Reset complete for %s", email_to_delete)
                    else:
                        logger.warning("No participant records found for %s", email_to_delete)
                else:
                    logger.warning("Participant found but no demographics record")
            else:
                logger.warning("No participant found for session_id: %s", session["session_id"])
        except Exception as e:
            logger.error("Error during session reset: %s", e)
            db.rollback()
        finally:
            db.close()
    else:
        logger.warning("No session_id in session")

    session.clear()
    logger.info("Session cleared, redirecting to start")
    return redirect(url_for('referral') if REQUIRE_REFERRAL else url_for('index'))


@app.route('/reset_session_confirm', methods=['POST'])
def reset_session_confirm():
    """Confirm session reset - calls the reset logic"""
    return reset_session_logic()


@app.route('/tutorial')
def tutorial():
    """Show tutorial mode - interactive walkthrough using real survey interface"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['version'] = SESSION_VERSION

    if not session.get('referral_validated', False):
        return redirect(url_for('referral'))

    demographics_completed = False
    if 'session_id' in session:
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            SELECT d.id FROM demographics d
            JOIN participants p ON d.participant_id = p.id
            WHERE p.session_id = ?
        ''', (session['session_id'],))
        demographics_completed = c.fetchone() is not None
        conn.close()

    if not demographics_completed:
        return redirect(url_for('index'))

    session['tutorial_mode'] = True
    return render_template('index.html', config=CONFIG,
                           tile_layout=TILE_LAYOUT,
                           show_prompt=SHOW_PROMPT,
                           tutorial_mode=True)


@app.route('/api/complete_tutorial', methods=['POST'])
def complete_tutorial():
    """Mark tutorial as completed"""
    if 'session_id' not in session:
        return jsonify({'error': 'No session'}), 400
    session['tutorial_completed'] = True
    session['tutorial_mode'] = False
    return jsonify({'ok': True})

# ---------------------------------------------------------------------------
# API - config
# ---------------------------------------------------------------------------

@app.route('/api/config')
def get_config():
    """Get configuration settings for frontend"""
    return jsonify({
        'dev_mode': DEV_MODE,
        'survey': SURVEY,
        'demographics': CONFIG.get('demographics', []),
        'inputs': CONFIG.get('inputs', []),
        'outputs': CONFIG.get('outputs', []),
        'questions': CONFIG.get('questions', []),
        'methods': CONFIG.get('methods', {}),
        'tutorial': CONFIG.get('tutorial', {}),
    })


@app.route('/api/check_demographics')
def check_demographics():
    """Check if demographics have been submitted for current session and get progress"""
    if 'session_id' not in session:
        return jsonify({'submitted': False})

    db = get_db()
    try:
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()

        if not participant:
            return jsonify({'submitted': False})

        demo = db.execute(
            'SELECT id, email FROM demographics WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()

        if not demo:
            return jsonify({'submitted': False})

        # Count completed pairs
        completed_pair_ids = _get_completed_trial_ids_for_email(demo['email'])

        return jsonify({
            'submitted': True,
            'completed_pairs': len(completed_pair_ids)
        })
    finally:
        db.close()

# ---------------------------------------------------------------------------
# API - demographics
# ---------------------------------------------------------------------------

@app.route('/api/submit_demographics', methods=['POST'])
@limiter.limit("10 per hour")
def submit_demographics():
    """Submit demographics information"""
    if 'session_id' not in session:
        return jsonify({'error': 'No session ID'}), 400

    data = request.json
    db = get_db()

    try:
        # Extract email using config-defined email field
        email = data.get(EMAIL_FIELD) if EMAIL_FIELD else None
        if isinstance(email, str):
            email = email.strip()
        is_retaking = False

        if email and not _valid_email(email):
            return jsonify({'error': 'Invalid email address'}), 400

        if email:
            previous_participant = db.execute('''
                SELECT p.id
                FROM participants p
                JOIN demographics d ON p.id = d.participant_id
                WHERE d.email = ?
                LIMIT 1
            ''', (email,)).fetchone()

            if previous_participant:
                response_count = db.execute(
                    'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
                    (previous_participant['id'],)
                ).fetchone()
                is_retaking = response_count and response_count['count'] > 0

                if is_retaking and data.get('confirm_retake'):
                    # Irreversible: only the retake modal's Confirm may destroy finished answers.
                    deleted_responses = db.execute('''
                        DELETE FROM survey_responses
                        WHERE participant_id IN (
                            SELECT p.id FROM participants p
                            JOIN demographics d ON p.id = d.participant_id
                            WHERE d.email = ?
                        )
                    ''', (email,)).rowcount
                    deleted_demographics = db.execute(
                        'DELETE FROM demographics WHERE email = ?', (email,)
                    ).rowcount
                    audit_log('RETAKE_DELETE', {
                        'email': email,
                        'responses_deleted': deleted_responses,
                        'demographics_deleted': deleted_demographics,
                    })

        # Create or get participant
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()

        if not participant:
            device_info = data.get('device_info', {})
            cursor = db.execute('''
                INSERT INTO participants
                (session_id, referral_code, browser, browser_version, os, screen_width, screen_height,
                 pixel_ratio, color_depth, viewport_width, viewport_height)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['session_id'],
                session.get('referral_code'),
                device_info.get('browser'),
                device_info.get('browser_version'),
                device_info.get('os'),
                device_info.get('screen_width'),
                device_info.get('screen_height'),
                device_info.get('pixel_ratio'),
                device_info.get('color_depth'),
                device_info.get('viewport_width'),
                device_info.get('viewport_height'),
            ))
            participant_id = cursor.lastrowid
        else:
            participant_id = participant['id']

        # Store demographics as JSON (email in dedicated column for indexing)
        demo_data = {k: v for k, v in data.items() if k != 'device_info'}
        db.execute('''
            INSERT INTO demographics (participant_id, email, data)
            VALUES (?, ?, ?)
        ''', (participant_id, email, json.dumps(demo_data)))

        db.commit()
        return jsonify({
            'success': True,
            'participant_id': participant_id,
            'is_retaking': is_retaking
        })
    except Exception as e:
        db.rollback()
        logger.error("Error in submit_demographics: %s", e)
        return jsonify({'error': 'An error occurred while submitting demographics'}), 500
    finally:
        db.close()

# ---------------------------------------------------------------------------
# API - trials
# ---------------------------------------------------------------------------

@app.route('/api/get_image_pair/<int:pair_index>')
def get_image_pair(pair_index):
    """Get a specific image pair for evaluation."""
    # Tutorial mode
    if session.get('tutorial_mode', False) and pair_index == 0:
        if TUTORIAL_PAIR:
            randomized = _randomize_pair('tutorial')
            stim = _build_stimulus_data(TUTORIAL_PAIR, randomized)
            stim['total_trials'] = 1
            # Also include flat fields for backward compat with current JS
            _add_flat_fields(stim, TUTORIAL_PAIR, randomized)
            return jsonify(stim)
        if IMAGE_PAIRS:
            randomized = _randomize_pair(IMAGE_PAIRS[0]['id'])
            stim = _build_stimulus_data(IMAGE_PAIRS[0], randomized)
            stim['total_trials'] = 1
            _add_flat_fields(stim, IMAGE_PAIRS[0], randomized)
            return jsonify(stim)
        return jsonify({'error': 'No image pairs available'}), 404

    # Initialize user's pair list
    if 'user_image_pairs' not in session or session.get('session_dev_mode') != DEV_MODE:
        user_email = _get_session_email()

        completed_pair_ids = _get_completed_trial_ids_for_email(user_email) if user_email else []
        available_pairs = [p for p in IMAGE_PAIRS if p['id'] not in completed_pair_ids]

        max_pairs = _trial_count()
        num_pairs = min(len(available_pairs), max_pairs)

        user_pairs = _assign_pairs(available_pairs, num_pairs)

        session['user_image_pairs'] = [pair['id'] for pair in user_pairs]
        session['user_pairs_count'] = len(user_pairs)
        session['session_dev_mode'] = DEV_MODE

    user_pair_ids = session.get('user_image_pairs', [])

    # The client counts indices against the assignment, so completed trials are skipped in place.
    completed_ids = set(_get_completed_trial_ids_for_email(_get_session_email()))
    position = pair_index
    while position < len(user_pair_ids) and user_pair_ids[position] in completed_ids:
        position += 1

    if position >= len(user_pair_ids):
        return jsonify({'error': 'Invalid image pair index'}), 404

    pair_id = user_pair_ids[position]
    trial = next((p for p in IMAGE_PAIRS if p['id'] == pair_id), None)

    if not trial:
        return jsonify({'error': 'Image pair not found'}), 404

    randomized = _randomize_pair(pair_id)
    # Answers are attributed from this record, never from what the browser posts back.
    pair_randomized = session.get('pair_randomized', {})
    pair_randomized[str(pair_id)] = randomized
    session['pair_randomized'] = pair_randomized

    stim = _build_stimulus_data(trial, randomized)
    stim['total_trials'] = len(user_pair_ids)
    stim['trials_remaining'] = len(user_pair_ids) - position

    # Add flat fields for backward compatibility with current JS
    _add_flat_fields(stim, trial, randomized)

    return jsonify(stim)


def _add_flat_fields(stim, trial, randomized):
    """Add flat top-level fields for backward compat with existing JS.

    The JS currently expects fields like data.prompt, data.image_a_url, etc.
    at the top level. We add these alongside the structured inputs/outputs.
    """
    methods_cfg = CONFIG['methods']

    # Flat method names
    if randomized:
        stim['method_a'] = trial.get(methods_cfg['b'], '')
        stim['method_b'] = trial.get(methods_cfg['a'], '')
    else:
        stim['method_a'] = trial.get(methods_cfg['a'], '')
        stim['method_b'] = trial.get(methods_cfg['b'], '')

    # Flat input columns
    for inp in CONFIG['inputs']:
        stim[inp['column']] = trial.get(inp['column'], '')

    # Flat output columns (with randomization)
    for out in CONFIG['outputs']:
        a_val = trial.get(out['column_a'], '')
        b_val = trial.get(out['column_b'], '')
        if randomized:
            a_val, b_val = b_val, a_val
        stim[out['column_a']] = a_val
        stim[out['column_b']] = b_val

    # Ensure id and other expected fields
    stim['id'] = trial['id']
    stim['was_randomized'] = randomized
    stim['total_pairs'] = stim.get('total_trials', 0)

# ---------------------------------------------------------------------------
# API - submit response
# ---------------------------------------------------------------------------

@app.route('/api/submit_survey', methods=['POST'])
@limiter.limit("60 per hour")
def submit_survey():
    """Submit survey response for a single trial."""
    if 'session_id' not in session:
        return jsonify({'error': 'No session ID'}), 400

    data = request.json
    db = get_db()

    try:
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()

        if not participant:
            return jsonify({'error': 'Participant not found'}), 404

        trial_id = data.get('image_pair_id')
        trial = next((p for p in IMAGE_PAIRS if p['id'] == trial_id), None)

        if trial is None:
            return jsonify({'error': 'Image pair not found'}), 404

        # The browser reports answers only; the served order is the session's record.
        randomized = bool(session.get('pair_randomized', {}).get(str(trial_id)))
        stimulus_data = _build_stimulus_data(trial, randomized)
        _add_flat_fields(stimulus_data, trial, randomized)
        for counter_key in ('total_trials', 'total_pairs'):
            stimulus_data.pop(counter_key, None)

        responses = data.get('responses')
        if not isinstance(responses, dict):
            return jsonify({'error': 'responses must be a structured object'}), 400

        stimulus_json = json.dumps(stimulus_data)
        responses_json = json.dumps(responses)
        was_randomized = 1 if randomized else 0
        # A non-number sits in this REAL column as text, and AVG() counts it as zero seconds.
        try:
            time_spent = float(data.get('time_spent'))
        except (TypeError, ValueError):
            time_spent = None

        existing = db.execute(
            'SELECT id FROM survey_responses WHERE participant_id = ? AND image_pair_id = ?',
            (participant['id'], trial_id)
        ).fetchone()

        if existing:
            db.execute('''
                UPDATE survey_responses
                SET stimulus_data = ?, responses = ?, was_randomized = ?,
                    time_spent = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (stimulus_json, responses_json, was_randomized, time_spent, existing['id']))
        else:
            db.execute('''
                INSERT INTO survey_responses
                (participant_id, image_pair_id, stimulus_data, responses, was_randomized, time_spent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (participant['id'], trial_id, stimulus_json, responses_json,
                  was_randomized, time_spent))

        user_pairs_count = session.get('user_pairs_count', _trial_count())
        db.commit()

        demo = db.execute(
            'SELECT email FROM demographics WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()

        if demo and demo['email']:
            completed_pair_ids = _get_completed_trial_ids_for_email(demo['email'])
            completed = len(completed_pair_ids) >= user_pairs_count
            if DEV_MODE:
                logger.debug("Submit check: email=%s, completed_pairs=%d, user_pairs_count=%d, completed=%s", demo["email"], len(completed_pair_ids), user_pairs_count, completed)
        else:
            completed = False

        return jsonify({'success': True, 'completed': completed})
    except Exception as e:
        db.rollback()
        logger.error("Error in submit_survey: %s", e)
        return jsonify({'error': 'An error occurred while submitting survey response'}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
# Credential guessing has no session to key on, so this one stays on the IP.
@limiter.limit("10 per hour", key_func=get_remote_address)
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        ip = get_remote_address()

        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            session.permanent = True
            audit_log('ADMIN_LOGIN_SUCCESS', {'ip': ip})
            return redirect(url_for('admin'))
        else:
            audit_log('ADMIN_LOGIN_FAILED', {'ip': ip, 'reason': 'Invalid password'})
            return render_template('admin_login.html', error='Invalid credentials', config=CONFIG), 401

    return render_template('admin_login.html', config=CONFIG)


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    if session.get('admin_authenticated'):
        audit_log('ADMIN_LOGOUT', {'ip': get_remote_address()})
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@require_admin
def admin():
    """Admin page to view results"""
    return render_template('admin.html', config=CONFIG)


_ADMIN_RESULTS_SELECT = '''
        SELECT
            p.session_id, p.referral_code, p.created_at as participant_created,
            p.browser, p.browser_version, p.os,
            p.screen_width, p.screen_height, p.pixel_ratio, p.color_depth,
            d.email, d.data as demographics_data,
            s.image_pair_id, s.stimulus_data, s.responses,
            s.was_randomized, s.time_spent, s.created_at as response_created
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        LEFT JOIN survey_responses s ON p.id = s.participant_id
        WHERE s.id IS NOT NULL
'''

ADMIN_PAGE_SIZE = 200
ADMIN_MAX_PAGE_SIZE = 1000


def _json_object(raw):
    """One JSON column as an object. Unparseable, or parsed to a non-object, reads as {}: the
    dashboard takes every row in one page, so one corrupt cell must not cost the analyst the view."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _flatten_result(row):
    """Expand one joined row's JSON columns into the flat fields the dashboard and CSV share."""
    r = dict(row)

    r.update(_json_object(r.get('demographics_data')))
    r.pop('demographics_data', None)

    stim = _json_object(r.get('stimulus_data'))
    methods = stim.get('methods', {})
    r['method_a'] = methods.get('a', stim.get('method_a', ''))
    r['method_b'] = methods.get('b', stim.get('method_b', ''))

    inputs = stim.get('inputs')
    for inp_name, inp_val in (inputs.items() if isinstance(inputs, dict) else []):
        r[f'input_{inp_name}'] = inp_val
    for key in ('prompt', 'image_a_url', 'image_b_url', 'identity_urls', 'mask_url'):
        if key in stim:
            r[key] = stim[key]
    r.pop('stimulus_data', None)

    resp = _json_object(r.get('responses'))

    for q_name, q_data in resp.items():
        if isinstance(q_data, dict):
            choice = q_data.get('choice', '')
            r[f'{q_name}_choice'] = choice
            r[f'{q_name}_confidence'] = q_data.get('confidence')
            if choice == 'A':
                r[f'{q_name}_preferred_method'] = r.get('method_a', '')
            elif choice == 'B':
                r[f'{q_name}_preferred_method'] = r.get('method_b', '')
            elif choice == 'equal':
                r[f'{q_name}_preferred_method'] = 'equal'
        else:
            r[q_name] = q_data
    r.pop('responses', None)
    return r


@app.route('/api/admin/results')
@require_admin
def admin_results():
    """One page of results; the dashboard polls this every 30s, so it must not ship the study."""
    limit = request.args.get('limit', ADMIN_PAGE_SIZE, type=int) or ADMIN_PAGE_SIZE
    limit = max(1, min(limit, ADMIN_MAX_PAGE_SIZE))
    offset = max(request.args.get('offset', 0, type=int) or 0, 0)

    db = get_db()
    rows = db.execute(
        _ADMIN_RESULTS_SELECT + ' ORDER BY s.created_at DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) AS n FROM survey_responses').fetchone()['n']
    db.close()

    return jsonify({
        'rows': [_flatten_result(r) for r in rows],
        'total': total,
        'limit': limit,
        'offset': offset,
    })


@app.route('/api/admin/stats')
@require_admin
def admin_stats():
    """Aggregate dashboard numbers: the counts the poll needs, not the rows behind them."""
    db = get_db()
    totals = db.execute('''
        SELECT COUNT(*) AS responses,
               COUNT(DISTINCT COALESCE(NULLIF(d.email, ''), p.session_id)) AS participants,
               AVG(s.time_spent) AS avg_time
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        JOIN survey_responses s ON s.participant_id = p.id
    ''').fetchone()
    raw = db.execute('SELECT stimulus_data, responses FROM survey_responses').fetchall()
    db.close()

    preferences = {}
    confidences = []
    for row in raw:
        flat = _flatten_result(row)
        for key, value in flat.items():
            if key.endswith('_preferred_method'):
                if value:
                    prefs = preferences.setdefault(key[:-len('_preferred_method')], {})
                    prefs[value] = prefs.get(value, 0) + 1
            elif key.endswith('_confidence') and value is not None:
                confidences.append(value)

    return jsonify({
        'responses': totals['responses'],
        'participants': totals['participants'],
        'avg_time': round(totals['avg_time'], 1) if totals['avg_time'] is not None else None,
        'avg_confidence': round(sum(confidences) / len(confidences), 1) if confidences else None,
        'preferences': preferences,
    })


@app.route('/api/admin/export')
@require_admin
def admin_export():
    """Export results as CSV"""
    import csv
    from io import StringIO

    db = get_db()
    results = db.execute('''
        SELECT
            p.session_id, p.referral_code, p.created_at as participant_created,
            p.browser, p.browser_version, p.os,
            p.screen_width, p.screen_height, p.pixel_ratio, p.color_depth,
            d.email, d.data as demographics_data,
            s.image_pair_id, s.stimulus_data, s.responses,
            s.was_randomized, s.time_spent, s.created_at as response_created
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        LEFT JOIN survey_responses s ON p.id = s.participant_id
        WHERE s.id IS NOT NULL
        ORDER BY p.id, s.image_pair_id
    ''').fetchall()
    db.close()

    flat = []
    all_keys = set()
    for row in results:
        r = _flatten_result(row)
        all_keys.update(r.keys())
        flat.append(r)

    output = StringIO()
    if flat:
        fieldnames = sorted(all_keys)
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for r in flat:
            writer.writerow(r)

    response = app.response_class(
        response=output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=survey_results.csv'}
    )
    return response


@app.route('/api/admin/delete_by_email', methods=['POST'])
@require_admin
@limiter.limit("20 per hour", key_func=get_remote_address)
def delete_by_email():
    """Delete all records associated with an email address"""
    email = request.json.get('email') if request.json else None

    if not email:
        audit_log('DELETE_FAILED', {'reason': 'No email provided'})
        return jsonify({'error': 'Email address is required'}), 400

    if not _valid_email(email):
        audit_log('DELETE_FAILED', {'reason': 'Invalid email format', 'email': str(email)[:50]})
        return jsonify({'error': 'Invalid email format'}), 400

    db = get_db()
    try:
        participant_ids = db.execute('''
            SELECT p.id
            FROM participants p
            JOIN demographics d ON p.id = d.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchall()

        if not participant_ids:
            audit_log('DELETE_NOT_FOUND', {'email': email})
            return jsonify({'error': 'No records found for this email address'}), 404

        participant_id_list = [p['id'] for p in participant_ids]
        placeholders = ','.join('?' * len(participant_id_list))

        responses_deleted = db.execute(
            f'DELETE FROM survey_responses WHERE participant_id IN ({placeholders})',
            participant_id_list
        ).rowcount
        demographics_deleted = db.execute(
            f'DELETE FROM demographics WHERE participant_id IN ({placeholders})',
            participant_id_list
        ).rowcount
        participants_deleted = db.execute(
            f'DELETE FROM participants WHERE id IN ({placeholders})',
            participant_id_list
        ).rowcount

        db.commit()

        audit_log('DELETE_SUCCESS', {
            'email': email,
            'participants_deleted': participants_deleted,
            'demographics_deleted': demographics_deleted,
            'responses_deleted': responses_deleted
        })

        return jsonify({
            'success': True,
            'email': email,
            'participants_deleted': participants_deleted,
            'demographics_deleted': demographics_deleted,
            'responses_deleted': responses_deleted
        })
    except Exception as e:
        db.rollback()
        audit_log('DELETE_ERROR', {'email': email, 'error': str(e)})
        return jsonify({'error': 'An error occurred while deleting records'}), 500
    finally:
        db.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
