from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort, send_from_directory
import csv
import sqlite3
import uuid
import os
import logging
import math
from datetime import datetime, timezone, timedelta
from io import StringIO
import json
import random
import hmac
import hashlib
import tempfile
from functools import lru_cache, wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from src.survey.config import load_config, get_email_field

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

# Trusts the one TLS hop production always has; untrusted, every client logs as the proxy's IP (F4).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# Security: Session configuration
# Only require HTTPS cookies in production
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Session timeout

# Security: CSRF Protection
app.config['WTF_CSRF_ENABLED'] = True
# One trial's answers are a few hundred bytes; this is the ceiling on what a POST may store.
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
app.config['WTF_CSRF_TIME_LIMIT'] = None  # Don't expire CSRF tokens
csrf = CSRFProtect(app)

# Security: Rate Limiting
def _participant_key():
    """Survey limits key on the participant, not the IP: a lab, office or conference NAT puts
    a whole cohort behind one address, and per-IP caps lock out everyone after the first."""
    return session.get('session_id') or get_remote_address()


RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

limiter = Limiter(
    app=app,
    key_func=_participant_key,
    default_limits=["1000 per hour"],
    storage_uri=RATELIMIT_STORAGE_URI,
)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change this in production
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'  # Set DEV_MODE=true for testing
if IS_PRODUCTION and DEV_MODE:
    raise ValueError("DEV_MODE must be false in production: it bypasses referral codes, shortens the study and turns on answer autofill")

# Session versioning - increment this when session structure changes
SESSION_VERSION = 3  # Incremented for config-driven schema change

# Under 1.0s a participant cannot have viewed three tiles and set two scales; the flag is what analysis filters on, the raw value is kept (study owner, 2026-11-04).
TIMING_FLOOR_S = 1.0

# Over 120s the browser clock was almost certainly running on a hidden tab, not on a judgement (study owner, 2026-11-05). Same flag, same rule: raw kept, analysis excludes.
TIMING_CEILING_S = 120.0

# Layout Configuration: Order of tiles in the three-tile grid
# Options: 'AMB' (A, Mask, B) or 'MAB' (Mask, A, B)
TILE_LAYOUT = os.environ.get('TILE_LAYOUT', 'MAB').upper()
if TILE_LAYOUT not in ['AMB', 'MAB']:
    logger.warning("Invalid TILE_LAYOUT '%s'. Using default 'MAB'. Valid options: AMB, MAB", TILE_LAYOUT)
    TILE_LAYOUT = 'MAB'

# The dashboard lists every participant email, so the shipped default is an open door.
if ADMIN_PASSWORD == 'admin123' and IS_PRODUCTION:
    raise ValueError("ADMIN_PASSWORD environment variable must be set in production!")

# A limit is only the cap the README quotes if every worker counts against the same counter.
# gunicorn runs several workers and a request lands on whichever picks it up, so an in-process
# store sees a fraction of one participant's traffic, and a restart wipes the tally.
if IS_PRODUCTION and not RATELIMIT_STORAGE_URI.startswith(('redis://', 'rediss://')):
    raise ValueError(
        "RATELIMIT_STORAGE_URI must be a redis:// URL in production: with the in-process store "
        "every gunicorn worker keeps its own counters, so the caps that protect admin login and "
        "delete-by-email are a multiple of the numbers documented")

# Audit log file
AUDIT_LOG_FILE = os.path.join(DATA_DIR, 'audit.log') if DATA_DIR else 'audit.log'

# Referral codes - Set valid codes via environment variable (comma-separated) or in code
# If empty, no referral code is required
REFERRAL_CODES_ENV = os.environ.get('REFERRAL_CODES', '')
# The form uppercases what it sends, so a stored code is normalised the same way: a lowercase entry could never admit anyone.
REFERRAL_CODES = set(code.strip().upper() for code in REFERRAL_CODES_ENV.split(',') if code.strip()) if REFERRAL_CODES_ENV else set()

# In dev mode, bypass referral code requirement
REQUIRE_REFERRAL = bool(REFERRAL_CODES) and not DEV_MODE

# Database location: DATA_DIR for production, local for development
DATABASE = os.path.join(DATA_DIR, 'survey.db') if DATA_DIR else os.path.join(tempfile.gettempdir(), 'juxtapose-dev', 'survey.db')

# ---------------------------------------------------------------------------
# Load survey configuration
# ---------------------------------------------------------------------------
CONFIG = load_config()
SURVEY = CONFIG['survey']
EMAIL_FIELD = get_email_field(CONFIG)

# Derive feature flags from config (env vars override)
_has_prompt_input = any(i['name'] == 'prompt' and i['type'] == 'text' for i in CONFIG.get('inputs', []))
# What the prompts do is stated by the study config, not by the environment: an env override here
# could render a prompt box for a study whose config has no prompt input, or hide the prompt of a
# study that has one. ENABLE_PROMPT_QUESTION went the same way - it was read by nothing.
SHOW_PROMPT = _has_prompt_input

# Tutorial pairs file
TUTORIAL_PAIRS_FILE = os.environ.get('TUTORIAL_PAIRS_FILE', 'examples/tutorial_image_pair.txt')

# ---------------------------------------------------------------------------
# Load trial data from TSV (config-driven columns)
# ---------------------------------------------------------------------------

def _trial_file_path(file_path_relative):
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, file_path_relative)


def _parse_trial_line(parts, columns, trial_id):
    """One split TSV line -> one trial row. Shared by the eager tutorial load and the on-demand
    store, so both agree on the optional-blank-is-None rule and the id numbering."""
    row = {}
    for i, col in enumerate(columns):
        val = parts[i].strip()
        # Treat empty strings as None for optional inputs
        inp = next((inp for inp in CONFIG['inputs'] if inp.get('column') == col), None)
        if inp and inp.get('optional') and not val:
            val = None
        row[col] = val
    row['id'] = trial_id
    return row


def _missing_file_message(file_path, file_path_relative):
    # Inventing placeholder trials here would collect real responses against fake stimuli.
    return (f"Trial data file not found: {file_path} "
            f"(data.file is '{file_path_relative}'; generate one with generate_pairs.py "
            "or set IMAGE_PAIRS_FILE)")


ROW_CACHE_SIZE = 512


@lru_cache(maxsize=ROW_CACHE_SIZE)
def _read_trial_row(path, offset, length, trial_id, columns):
    """One trial row, parsed from its byte range, cached by the position it came from.

    lru_cache is the bound and the thread-safety: the store used to keep its own OrderedDict and
    evict it by hand from every request thread, which is a check-then-act waiting to break. Two
    threads may parse the same row concurrently, which costs a parse and changes nothing - the
    work is pure.
    """
    with open(path, 'rb') as f:
        f.seek(offset)
        line = f.read(length)
    return _parse_trial_line(line.decode('utf-8').rstrip('\r\n').split('\t'), list(columns), trial_id)


class TrialStore:
    """The study's trials, indexed at boot and parsed on demand.

    A study of N pairs used to cost N dicts in every worker, and each pair request scanned that list
    for its id. Boot now keeps an id and a byte range per row; a row becomes a dict when a
    participant is served it, and _read_trial_row keeps the most recent ROW_CACHE_SIZE hot.
    """

    def __init__(self, file_path_relative, start_id=1):
        self.relative_path = file_path_relative
        self.path = _trial_file_path(file_path_relative)
        self.columns = CONFIG['data']['columns']
        self.ids = []
        self._offsets = {}
        self._index(start_id)

    def _index(self, start_id):
        trial_id = start_id
        offset = 0
        try:
            with open(self.path, 'rb') as f:
                for line in f:
                    text = line.decode('utf-8').rstrip('\r\n')
                    if text and not text.startswith('#'):
                        parts = text.split('\t')
                        if len(parts) != len(self.columns):
                            logger.warning("Line %d has %d fields (expected %d), skipping",
                                           trial_id, len(parts), len(self.columns))
                        else:
                            self.ids.append(trial_id)
                            self._offsets[trial_id] = (offset, len(line))
                            trial_id += 1
                    offset += len(line)
        except FileNotFoundError:
            raise FileNotFoundError(_missing_file_message(self.path, self.relative_path)) from None

        if not self.ids:
            raise ValueError(f"No valid trials found in {self.relative_path}")
        logger.info("Indexed %d image pairs from %s", len(self.ids), self.relative_path)

    def get(self, trial_id):
        """One trial row, parsed from its byte range on first use."""
        location = self._offsets.get(trial_id)
        if location is None:
            return None
        return _read_trial_row(self.path, location[0], location[1], trial_id, tuple(self.columns))

    def first(self):
        return self.get(self.ids[0]) if self.ids else None

    @property
    def count(self):
        return len(self.ids)


def load_image_pairs():
    """The study's trials: ids and byte ranges at boot, rows when served."""
    data_file = os.environ.get('IMAGE_PAIRS_FILE', CONFIG['data']['file'])
    return TrialStore(data_file, start_id=1)


def load_tutorial_pair():
    """The walkthrough's one pair, read the way a study row is read."""
    try:
        return TrialStore(TUTORIAL_PAIRS_FILE, start_id=0).first()
    except Exception as e:
        logger.warning("Could not load tutorial pair: %s", e)
        return IMAGE_PAIRS.first()


# Load image pairs on startup
IMAGE_PAIRS = load_image_pairs()
TUTORIAL_PAIR = load_tutorial_pair()

# Security: Audit logging
def _pii_hash(value):
    """A stable, short hash: rows about one participant or one code stay joinable without the value
    itself living in a wider-read operational file."""
    return hashlib.sha256(value.strip().lower().encode('utf-8')).hexdigest()[:16]


def _redact_audit_details(details):
    """Participant emails are PII and audit.log is an operational file; a stable hash keeps rows
    about one participant joinable without copying the address into a wider-read file."""
    if not isinstance(details, dict):
        return details
    redacted = dict(details)
    for key, value in redacted.items():
        if key.endswith('email') and isinstance(value, str) and value:
            redacted[key] = _pii_hash(value)
    return redacted


def audit_log(action, details, user_ip=None):
    """Log security-sensitive actions"""
    try:
        # CURRENT_TIMESTAMP in the database is UTC; a local stamp here cannot be joined to the row
        # it explains. Entries before 2026-11-05 carry server-local stamps (docs/audit-findings.md).
        timestamp = datetime.now(timezone.utc).isoformat()
        ip = user_ip or get_remote_address()
        session_id = session.get('session_id', 'unknown')
        admin_session = 'ADMIN' if session.get('admin_authenticated') else 'USER'

        log_entry = {
            'timestamp': timestamp,
            'ip': ip,
            'session': session_id,
            'role': admin_session,
            'action': action,
            'details': _redact_audit_details(details)
        }

        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')

    except Exception as e:
        # Never let audit logging break the app
        logger.error("Audit logging error: %s", e)

# The stale-session gate is a security behaviour, so its opt-out is named, not borrowed from a
# general test knob: hanging it off Flask's TESTING flag meant every suite, by setting TESTING,
# stopped exercising the one check that protects a participant mid-study across a deploy.
SESSION_GATE_DISABLED = os.environ.get('SURVEY_DISABLE_SESSION_GATE', 'false').lower() == 'true'
if IS_PRODUCTION and SESSION_GATE_DISABLED:
    raise ValueError("SURVEY_DISABLE_SESSION_GATE must not be set in production: it is how a session "
                     "built for an older schema gets served a config it was not built for")


# Session validation: Check for stale sessions
@app.before_request
def validate_session():
    """Validate session version and clear if stale"""
    if request.path.startswith('/static/'):
        return
    if SESSION_GATE_DISABLED:
        return
    if 'session_id' in session:
        session_version = session.get('version')
        if session_version != SESSION_VERSION:
            logger.info("Clearing stale session (version %s != %s)", session_version, SESSION_VERSION)
            session.clear()

# The gate redirects the pages, and the API is the study: on HEAD a session that never entered a code stored an answer through it (F2).
@app.before_request
def require_referral_for_study_api():
    if REQUIRE_REFERRAL and not session.get('referral_validated') \
            and request.path.startswith('/api/'):
        abort(403)


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
    # Without busy_timeout a contended volume 500s a paying participant's submit; WAL keeps readers off the writer's queue.
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=5000')
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
            FOREIGN KEY (participant_id) REFERENCES participants (id),
            UNIQUE (participant_id)
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
            timing_flag INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id),
            UNIQUE (participant_id, image_pair_id)
        )
    ''')

    # IF NOT EXISTS, so a study database predating this gets indexed on its next boot.
    db.execute('CREATE INDEX IF NOT EXISTS idx_demographics_email ON demographics (email)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_responses_participant ON survey_responses (participant_id)')

    # The stats cache's version: an updated answer changes neither the answer count nor the newest timestamp.
    db.execute('''
        CREATE TABLE IF NOT EXISTS stats_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            n INTEGER NOT NULL
        )
    ''')
    db.execute('INSERT OR IGNORE INTO stats_version (id, n) VALUES (1, 0)')
    for event in ('INSERT', 'UPDATE', 'DELETE'):
        db.execute(f'''
            CREATE TRIGGER IF NOT EXISTS survey_responses_{event.lower()}_bumps_stats
            AFTER {event} ON survey_responses
            BEGIN
                UPDATE stats_version SET n = n + 1 WHERE id = 1;
            END
        ''')

    columns = {row['name'] for row in db.execute('PRAGMA table_info(survey_responses)')}
    if 'timing_flag' not in columns:
        db.execute('ALTER TABLE survey_responses ADD COLUMN timing_flag INTEGER DEFAULT 0')

    # Two demographics rows for one participant make the admin join report each of their answers twice.
    db.execute('''
        DELETE FROM demographics
        WHERE id NOT IN (SELECT MAX(id) FROM demographics GROUP BY participant_id)
    ''')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_demographics_participant '
               'ON demographics (participant_id)')

    # Same for answers: a trial is answered once, so the newest row per (participant, trial) wins.
    db.execute('''
        DELETE FROM survey_responses
        WHERE id NOT IN (SELECT MAX(id) FROM survey_responses GROUP BY participant_id, image_pair_id)
    ''')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_responses_participant_pair '
               'ON survey_responses (participant_id, image_pair_id)')

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
    return min(IMAGE_PAIRS.count, max_pairs)


def _assign_pairs(available_ids, num_pairs):
    """The trials this participant takes, in order. Under E2E_RANDOM_SEED the draw comes from a
    generator keyed to the session, so an extra pair request cannot shift the assignment by consuming
    a stream draw; production keeps the module stream. Keyed per session on purpose - per-participant
    variety is the counterbalancing, unlike the A/B flip, which must not follow the session id."""
    seed = os.environ.get('E2E_RANDOM_SEED')
    rng = random.Random(f'{seed}:{session.get("session_id")}') if seed else random
    pairs = list(available_ids)
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


def _get_session_email(db=None):
    """Email of the participant this session submitted demographics for, None before that.

    For the two questions about a person rather than a session: retake detection, and the
    pairs_per_user cap. Takes a connection from a caller that has one.
    """
    if 'session_id' not in session:
        return None
    own_connection = db is None
    if own_connection:
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
        if own_connection:
            db.close()


def _get_session_participant_id(db=None):
    """Row id of the participant this session owns, None before its intake is stored.

    Every progress question the app answers is about one session's own rows, and the participant
    row is what a session owns; the email is a claim in a form, and a study may collect none.
    """
    if 'session_id' not in session:
        return None
    own_connection = db is None
    if own_connection:
        db = get_db()
    try:
        row = db.execute('SELECT id FROM participants WHERE session_id = ?',
                         (session['session_id'],)).fetchone()
        return row['id'] if row else None
    finally:
        if own_connection:
            db.close()


def _question_shown(question, inputs):
    """The page's own visibility rule: a depends_on question shows when that input has a value.

    The stored stimulus input is the only record of what the participant was shown, so the server
    asks it rather than exempting every depends_on question from the completeness rule.
    """
    name = question.get('depends_on')
    if not name or name not in inputs:
        return True
    return str(inputs[name] or '').strip() != ''


def _completed_trial_ids(rows):
    """The trials in `rows` - (image_pair_id, responses, stimulus_data) - whose shown questions are answered."""
    completed = []
    required_questions = [q for q in CONFIG['questions'] if q.get('required') or q['type'] == 'ab_preference']

    for row in rows:
        try:
            resp = json.loads(row['responses'])
            inputs = json.loads(row['stimulus_data'] or '{}').get('inputs') or {}
        except (json.JSONDecodeError, TypeError):
            continue

        all_answered = True
        for q in required_questions:
            q_resp = resp.get(q['name'])
            if not q_resp:
                if not _question_shown(q, inputs):
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
            if q['type'] == 'free_text' and not str(q_resp.get('text') or '').strip():
                # The page posts {text: ''} for an empty box, and a dict holding '' is truthy.
                all_answered = False
                break
            if q['type'] in ('likert', 'multiple_choice') and q_resp.get('value') is None:
                all_answered = False
                break

        if all_answered:
            completed.append(row['image_pair_id'])

    return completed


def _get_completed_trial_ids(participant_id, email=None, db=None):
    """Trials answered: this participant's own rows, plus the address's other rows when told.

    Two keys for two promises. Progress is a session's own work - keyed on the email alone, a
    study that collects none had nothing to count and its participants never finished. The
    pairs_per_user cap is a person's, so `email` adds an address's earlier rows and a returner in
    a new browser is not handed the whole set again.
    """
    if not participant_id and not email:
        return []

    own_connection = db is None
    if own_connection:
        db = get_db()
    try:
        rows = db.execute('''
            SELECT DISTINCT image_pair_id, responses, stimulus_data
            FROM survey_responses
            WHERE responses IS NOT NULL
                AND (participant_id = ?
                     OR (? IS NOT NULL AND participant_id IN
                         (SELECT participant_id FROM demographics WHERE email = ?)))
        ''', (participant_id, email, email)).fetchall()
        return _completed_trial_ids(rows)
    finally:
        if own_connection:
            db.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    """Simple health check endpoint for monitoring"""
    # /health is unauthenticated: it must not name where the study's answers live.
    return jsonify({
        'status': 'healthy',
        'pairs_loaded': IMAGE_PAIRS.count,
        'dev_mode': DEV_MODE,
    }), 200


INTAKE_CELL_MAX = 2000


@app.context_processor
def inject_template_limits():
    """The page caps what the app refuses, from one number."""
    return {'INTAKE_CELL_MAX': INTAKE_CELL_MAX}
DEVICE_TEXT_MAX = 100
DEVICE_NUMBER_KEYS = ('screen_width', 'screen_height', 'pixel_ratio', 'color_depth',
                      'viewport_width', 'viewport_height')
DEVICE_TEXT_KEYS = ('browser', 'browser_version', 'os')


def _device_info_error(device):
    """These nine values land in typed columns, so one sqlite cannot bind refuses the whole intake."""
    if not isinstance(device, dict):
        return "device_info must be an object of the browser's own settings"
    for key in DEVICE_NUMBER_KEYS:
        value = device.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            return f"device_info.{key} must be a number"
    for key in DEVICE_TEXT_KEYS:
        value = device.get(key)
        if value is not None and not isinstance(value, str):
            return f"device_info.{key} must be text"
        if isinstance(value, str) and len(value) > DEVICE_TEXT_MAX:
            return f"device_info.{key} must be at most {DEVICE_TEXT_MAX} characters"
    return None


def _intake_error(data):
    """The intake's own rules, from the config: an html `required` attribute binds the browser, not the app."""
    if 'device_info' in data:
        # Before the field loop: a nested value here reaches sqlite and the route answers 500.
        device_error = _device_info_error(data['device_info'])
        if device_error:
            return device_error
    if CONFIG['survey'].get('consent_text') and not str(data.get('consent') or '').strip():
        return "Field 'consent' is required: this study asks for agreement before the intake"
    for field in CONFIG.get('demographics', []):
        name, kind = field['name'], field.get('type')
        cells = data.get(name)
        cells = cells if isinstance(cells, list) else [cells]
        if kind == 'checkbox':
            # The page joins a ticked group into one 'a, b' string (study-state.normalizeDemographics).
            cells = [part.strip() for cell in cells if isinstance(cell, str) for part in cell.split(',')]
        texts = []
        for cell in cells:
            if cell is None:
                continue
            if not isinstance(cell, (str, int, float, bool)):
                return f"Field '{name}' must be text or a list of text"
            if str(cell).strip():
                texts.append(str(cell))
        if field.get('required') and not texts:
            return f"Field '{name}' is required"
        if kind in ('select', 'radio', 'checkbox'):
            # 'none' is the page's own word for a checkbox group with nothing ticked.
            allowed = {str(o.get('value')) for o in field.get('options', [])}
            if kind == 'checkbox':
                allowed.add('none')
            if any(text not in allowed for text in texts):
                return f"Field '{name}' must be one of {', '.join(sorted(allowed))}"
        if any(len(text) > INTAKE_CELL_MAX for text in texts):
            return f"Field '{name}' must be at most {INTAKE_CELL_MAX} characters"
    return None


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
        # Without this the cookie dies with the browser, and PERMANENT_SESSION_LIFETIME configures nothing.
        session.permanent = True

    if REQUIRE_REFERRAL and not session.get('referral_validated'):
        return redirect(url_for('referral'))

    force_new = request.args.get('new') == 'true'

    db = get_db()
    participant = db.execute(
        'SELECT id FROM participants WHERE session_id = ?',
        (session['session_id'],)
    ).fetchone()

    if participant:
        email = _get_session_email(db)
        db.close()
        # "Has this person finished?" spans the address's rows: a returner who finished in an earlier browser must not be sent back through the study.
        completed_pair_ids = _get_completed_trial_ids(participant['id'], email)
        expected_pairs = _trial_count()

        if DEV_MODE:
            logger.debug("Index route check: participant=%s, completed=%d, expected=%d, tutorial_complete=%s", participant["id"], len(completed_pair_ids), expected_pairs, session.get("tutorial_completed", False))

        if len(completed_pair_ids) >= expected_pairs:
            if DEV_MODE and force_new:
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
# The code is a shared bearer token: per-session limits are free, so guessing must ride the IP cap the login page uses (F8).
@limiter.limit("20 per hour", key_func=get_remote_address)
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
            # The code is a shared bearer token with no expiry: which code admitted which session is
            # the only way to trace contaminated responses back to a leak. Hashed, as emails are.
            audit_log('REFERRAL_ACCEPTED', {'referral_code_hash': _pii_hash(code)})
            return redirect(url_for('index'))
        else:
            audit_log('REFERRAL_REJECTED', {'reason': 'Invalid referral code'})
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
        # Without this the cookie dies with the browser, and PERMANENT_SESSION_LIFETIME configures nothing.
        session.permanent = True

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
        completed_pair_ids = _get_completed_trial_ids(participant['id'])

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
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected a JSON object'}), 400
    intake_error = _intake_error(data)
    if intake_error:
        return jsonify({'error': intake_error}), 400
    db = get_db()

    try:
        # Read before any write: this session's own address is the only proof a confirm may delete for it (audit 6 F1).
        session_email = _get_session_email(db)
        # Extract email using config-defined email field
        email = data.get(EMAIL_FIELD) if EMAIL_FIELD else None
        if isinstance(email, str):
            email = email.strip()
        is_retaking = False

        if email and not _valid_email(email):
            return jsonify({'error': 'Invalid email address'}), 400

        if email:
            # Counted over the same accounts the confirm below deletes: one account's share is not the answer to "will this erase finished work?".
            answered = db.execute('''
                SELECT COUNT(*)
                FROM survey_responses s
                WHERE s.participant_id IN (
                    SELECT p.id FROM participants p
                    JOIN demographics d ON p.id = d.participant_id
                    WHERE d.email = ?
                )
            ''', (email,)).fetchone()[0]
            is_retaking = answered > 0

            if is_retaking and data.get('confirm_retake'):
                # The email is a claim in the body, not an identity: unowned, one POST from a free session wiped any participant (audit 6 F1).
                if session_email is None or session_email != email:
                    audit_log('RETAKE_DELETE_REFUSED',
                              {'reason': 'session does not own this email', 'email': email})
                    return jsonify({'error':
                                    'This session has not submitted demographics for this address'}), 403

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
        # Only what the study declares is intake; `consent` rides with it (survey.consent_text).
        declared = {field['name'] for field in CONFIG.get('demographics', [])} | {'consent'}
        demo_data = {k: v for k, v in data.items() if k in declared}
        db.execute('DELETE FROM demographics WHERE participant_id = ?', (participant_id,))
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
        first_pair = IMAGE_PAIRS.first()
        if first_pair:
            randomized = _randomize_pair(first_pair['id'])
            stim = _build_stimulus_data(first_pair, randomized)
            stim['total_trials'] = 1
            _add_flat_fields(stim, first_pair, randomized)
            return jsonify(stim)
        return jsonify({'error': 'No image pairs available'}), 404

    # One connection, one read, both keys: this session's own rows, and its address's earlier ones for the cap.
    db = get_db()
    try:
        participant_id = _get_session_participant_id(db)
        completed_ids = set(_get_completed_trial_ids(participant_id,
                                                    _get_session_email(db), db))
    finally:
        db.close()

    if participant_id is None:
        # The intake is the study's front door: an html `required` attribute stopped the browser, not this endpoint.
        return jsonify({'error': 'Demographics not submitted'}), 403

    # Initialize user's pair list
    if 'user_image_pairs' not in session or session.get('session_dev_mode') != DEV_MODE:
        available_ids = [pid for pid in IMAGE_PAIRS.ids if pid not in completed_ids]

        # The pairs_per_user cap counts every trial this participant answered, so assign only what is left.
        num_pairs = min(len(available_ids), max(0, _trial_count() - len(completed_ids)))

        user_pair_ids = _assign_pairs(available_ids, num_pairs)

        session['user_image_pairs'] = user_pair_ids
        session['user_pairs_count'] = len(user_pair_ids)
        session['session_dev_mode'] = DEV_MODE

    user_pair_ids = session.get('user_image_pairs', [])

    # The client counts indices against the assignment, so completed trials are skipped in place.
    position = pair_index
    while position < len(user_pair_ids) and user_pair_ids[position] in completed_ids:
        position += 1

    if position >= len(user_pair_ids):
        return jsonify({'error': 'Invalid image pair index'}), 404

    pair_id = user_pair_ids[position]
    trial = IMAGE_PAIRS.get(pair_id)

    if not trial:
        return jsonify({'error': 'Image pair not found'}), 404

    pair_randomized = session.get('pair_randomized', {})
    # One draw per (session, trial), and the answer is attributed from this record, never from what the browser posts back.
    if str(pair_id) not in pair_randomized:
        pair_randomized[str(pair_id)] = _randomize_pair(pair_id)
        session['pair_randomized'] = pair_randomized
    randomized = pair_randomized[str(pair_id)]

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

_AB_CHOICES = ('A', 'B', 'equal')


def _off_scale(name, value, scale, label):
    """Describe a rating outside 1..scale, or None. A missing rating is an unanswered question, not a bad one."""
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not float(value).is_integer() or not 1 <= value <= scale):
        return f"{name} {label} must be a whole number from 1 to {scale}"
    return None


def _invalid_answer(question, answer):
    """Describe an answer this study's page could not have produced, or None.

    The dashboard averages what is stored, so a posted number off the scale becomes the study's
    reported result - the form's own range is the only rule that keeps it out.
    """
    if not isinstance(answer, dict):
        return f"{question['name']} is not an answer"

    kind = question['type']
    if kind == 'ab_preference':
        choice = answer.get('choice')
        if choice is not None and choice not in _AB_CHOICES:
            return f"{question['name']} choice must be one of {'/'.join(_AB_CHOICES)}"
        confidence = answer.get('confidence')
        if not question.get('confidence'):
            return None if confidence is None else f"{question['name']} records no confidence"
        return _off_scale(question['name'], confidence, 5, 'confidence')

    if kind == 'likert':
        return _off_scale(question['name'], answer.get('value'), question.get('scale', 5), 'value')

    if kind == 'free_text':
        text = answer.get('text')
        if isinstance(text, str) and len(text) > INTAKE_CELL_MAX:
            return (f"{question['name']} text must be at most {INTAKE_CELL_MAX} characters: "
                    "it is shipped to the dashboard on every poll")
        return None

    if kind == 'multiple_choice':
        value = answer.get('value')
        options = {option['value'] for option in question.get('options', [])}
        if value is not None and value not in options:
            return f"{question['name']} value must be one of {', '.join(sorted(options))}"

    return None


@app.route('/api/submit_survey', methods=['POST'])
# The study length plus headroom for a re-answered trial; a cap under the study 429s the trial that ends it.
@limiter.limit(lambda: f"{_trial_count() + 20} per hour")
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
        trial = IMAGE_PAIRS.get(trial_id)

        if trial is None:
            return jsonify({'error': 'Image pair not found'}), 404

        if trial_id not in session.get('user_image_pairs', []):
            return jsonify({'error': 'Image pair was not served to this session'}), 400

        # The browser reports answers only; the served order is the session's record.
        randomized = bool(session.get('pair_randomized', {}).get(str(trial_id)))
        stimulus_data = _build_stimulus_data(trial, randomized)
        _add_flat_fields(stimulus_data, trial, randomized)
        for counter_key in ('total_trials', 'total_pairs'):
            stimulus_data.pop(counter_key, None)

        responses = data.get('responses')
        if not isinstance(responses, dict):
            return jsonify({'error': 'responses must be a structured object'}), 400

        unknown = sorted(set(responses) - {q['name'] for q in CONFIG['questions']})
        if unknown:
            return jsonify({'error': f"responses has questions this study does not ask: {', '.join(unknown)}"}), 400

        for question in CONFIG['questions']:
            answer = responses.get(question['name'])
            if answer is None:
                continue
            problem = _invalid_answer(question, answer)
            if problem:
                return jsonify({'error': problem}), 400

        stimulus_json = json.dumps(stimulus_data)
        responses_json = json.dumps(responses)
        was_randomized = 1 if randomized else 0
        # A non-number sits in this REAL column as text, and AVG() counts it as zero seconds.
        try:
            time_spent = float(data.get('time_spent'))
        except (TypeError, ValueError):
            time_spent = None
        # JSON spells Infinity and -Infinity, and a REAL column carries them into every report of it.
        if time_spent is not None and not math.isfinite(time_spent):
            time_spent = None
        timing_flag = 1 if time_spent is not None and (
                         time_spent < TIMING_FLOOR_S or time_spent > TIMING_CEILING_S) else 0

        db.execute('''
            INSERT INTO survey_responses
            (participant_id, image_pair_id, stimulus_data, responses, was_randomized, time_spent, timing_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (participant_id, image_pair_id) DO UPDATE SET
                stimulus_data = excluded.stimulus_data,
                responses = excluded.responses,
                was_randomized = excluded.was_randomized,
                time_spent = excluded.time_spent,
                timing_flag = excluded.timing_flag,
                created_at = CURRENT_TIMESTAMP
        ''', (participant['id'], trial_id, stimulus_json, responses_json,
              was_randomized, time_spent, timing_flag))

        user_pairs_count = session.get('user_pairs_count', _trial_count())
        db.commit()

        # Counted on this session's own rows: an earlier account's answers under the same email are not its progress.
        completed_pair_ids = _get_completed_trial_ids(participant['id'])
        served = set(session.get('user_image_pairs', []))
        session_pairs_done = len(served.intersection(completed_pair_ids))
        completed = session_pairs_done >= user_pairs_count
        if DEV_MODE:
            logger.debug("Submit check: participant=%s, session_pairs_done=%d of %d, user_pairs_count=%d, completed=%s", participant["id"], session_pairs_done, len(served), user_pairs_count, completed)

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

        # Bytes, not str: compare_digest raises TypeError on non-ASCII strings, which 500'd every login with an accented password (audit 6 F4).
        if hmac.compare_digest((password or '').encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
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


def _csv_safe(value):
    """Excel runs a cell starting with = + - @, tab or CR, and participant answers are the cell's author here."""
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{value}"
    return value


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
            # Only the A/B answer has `choice`; likert/multiple_choice carry `value`, free text carries `text`.
            choice = q_data.get('choice')
            if choice is not None:
                r[f'{q_name}_choice'] = choice
                r[f'{q_name}_confidence'] = q_data.get('confidence')
                if choice == 'A':
                    r[f'{q_name}_preferred_method'] = r.get('method_a', '')
                elif choice == 'B':
                    r[f'{q_name}_preferred_method'] = r.get('method_b', '')
                elif choice == 'equal':
                    r[f'{q_name}_preferred_method'] = 'equal'
            for key in ('value', 'text'):
                if key in q_data:
                    r[f'{q_name}_{key}'] = q_data[key]
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
        # Newest-first on a second-granularity timestamp gives no order inside a second, and every
        # answer that lands while the analyst pages shifts the window: one row on two pages.
        _ADMIN_RESULTS_SELECT + ' ORDER BY s.id LIMIT ? OFFSET ?',
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


_STATS_CACHE = {}


def _stats_rows(db):
    """Every answer row, the raw material of the preference and confidence aggregates."""
    return db.execute('SELECT stimulus_data, responses FROM survey_responses').fetchall()


@app.route('/api/admin/stats')
@require_admin
def admin_stats():
    """Aggregate dashboard numbers: the counts the poll needs, not the rows behind them."""
    db = get_db()
    totals = db.execute('''
        SELECT COUNT(*) AS responses,
               COUNT(DISTINCT COALESCE(NULLIF(d.email, ''), p.session_id)) AS participants,
               AVG(CASE WHEN COALESCE(s.timing_flag, 0) = 0 THEN s.time_spent END) AS avg_time
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        JOIN survey_responses s ON s.participant_id = p.id
    ''').fetchone()
    # The dashboard polls this on a timer and the aggregate parses every answer row, so the cached study is versioned by that counter.
    version = db.execute('SELECT n FROM stats_version WHERE id = 1').fetchone()['n']
    cache_key = version
    cached = _STATS_CACHE.get(cache_key)
    if cached is None:
        preferences = {}
        confidences = []
        for row in _stats_rows(db):
            flat = _flatten_result(row)
            for key, value in flat.items():
                if key.endswith('_preferred_method'):
                    if value:
                        prefs = preferences.setdefault(key[:-len('_preferred_method')], {})
                        prefs[value] = prefs.get(value, 0) + 1
                elif key.endswith('_confidence') and isinstance(value, (int, float)):
                    # Answers arrive as the browser posted them: a non-number here raised on every poll, forever.
                    confidences.append(value)
        cached = (preferences, confidences)
        _STATS_CACHE.clear()
        _STATS_CACHE[cache_key] = cached
    db.close()
    preferences, confidences = cached

    return jsonify({
        'responses': totals['responses'],
        'participants': totals['participants'],
        'avg_time': round(totals['avg_time'], 1) if totals['avg_time'] is not None else None,
        'avg_confidence': round(sum(confidences) / len(confidences), 1) if confidences else None,
        'preferences': preferences,
    })


_PARTICIPANT_CACHE = {}


def _participant_rollup(db):
    """{participant id: (answers, trials completed)} for every participant with answers.

    Completion is the app's one rule over stored answers, not a SQL count, so this reads the answer
    rows the way the stats aggregate does and caches by the same counter the dashboard poll uses.
    """
    version = db.execute('SELECT n FROM stats_version WHERE id = 1').fetchone()['n']
    cached = _PARTICIPANT_CACHE.get(version)
    if cached is not None:
        return cached

    by_participant = {}
    for row in db.execute('SELECT participant_id, image_pair_id, responses, stimulus_data '
                          'FROM survey_responses'):
        by_participant.setdefault(row['participant_id'], []).append(row)
    rollup = {pid: (len(rows), len(_completed_trial_ids(rows)))
              for pid, rows in by_participant.items()}
    _PARTICIPANT_CACHE.clear()
    _PARTICIPANT_CACHE[version] = rollup
    return rollup


@app.route('/api/admin/participants')
@require_admin
def admin_participants():
    """The roster: one row per participant with their own progress, and where the study loses people.

    The results page is paged by response, so grouping it in the browser listed only the
    participants inside that window - the audit read 14 of 30 people there and one participant's
    truncated 5 answers as a dropout at trial 5.
    """
    limit = request.args.get('limit', ADMIN_PAGE_SIZE, type=int) or ADMIN_PAGE_SIZE
    limit = max(1, min(limit, ADMIN_MAX_PAGE_SIZE))
    offset = max(request.args.get('offset', 0, type=int) or 0, 0)

    db = get_db()
    total = db.execute('SELECT COUNT(*) AS n FROM participants').fetchone()['n']
    rows = db.execute('''
        SELECT p.id, p.session_id, p.referral_code, p.browser, p.browser_version, p.os,
               p.screen_width, p.screen_height, p.created_at, d.email, d.data AS demographics
        FROM participants p
        LEFT JOIN demographics d ON d.participant_id = p.id
        ORDER BY p.id LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()
    rollup = _participant_rollup(db)
    db.close()

    pairs_per_user = _trial_count()
    counts = [completed for _answers, completed in rollup.values()]
    dropout = {}
    for count in counts + [0] * (total - len(rollup)):
        if count < pairs_per_user:
            dropout[str(count)] = dropout.get(str(count), 0) + 1

    return jsonify({
        'rows': [{
            **_json_object(row['demographics']),
            'id': row['id'],
            'session_id': row['session_id'],
            'email': row['email'],
            'referral_code': row['referral_code'],
            'browser': row['browser'],
            'browser_version': row['browser_version'],
            'os': row['os'],
            'screen_width': row['screen_width'],
            'screen_height': row['screen_height'],
            'created_at': row['created_at'],
            'responses': rollup.get(row['id'], (0, 0))[0],
            'trials_completed': rollup.get(row['id'], (0, 0))[1],
            'pairs_per_user': pairs_per_user,
        } for row in rows],
        'total': total,
        'limit': limit,
        'offset': offset,
        'summary': {
            'started': total,
            'completed': sum(1 for count in counts if count >= pairs_per_user),
            'pairs_per_user': pairs_per_user,
            'dropout': dropout,
        },
    })


@app.route('/api/admin/export')
@require_admin
def admin_export():
    """Export results as CSV."""
    fieldnames = _export_fieldnames()
    db = get_db()
    try:
        rows = db.execute('SELECT COUNT(*) AS n' + _EXPORT_FROM).fetchone()['n']
    finally:
        db.close()

    # This is the one admin action that copies every participant email out of the database.
    audit_log('EXPORT_CSV', {'rows': rows, 'columns': len(fieldnames)})

    return app.response_class(
        response=_stream_csv(fieldnames),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=survey_results.csv'}
    )


# The columns every row carries because the SELECT and _flatten_result always produce them.
_EXPORT_COLUMNS = (
    'session_id', 'referral_code', 'participant_created', 'browser', 'browser_version', 'os',
    'screen_width', 'screen_height', 'pixel_ratio', 'color_depth', 'email', 'consent',
    'image_pair_id', 'was_randomized', 'time_spent', 'timing_flag', 'response_created',
    'method_a', 'method_b', 'prompt', 'image_a_url', 'image_b_url', 'identity_urls', 'mask_url',
)

_EXPORT_SELECT = '''
            p.session_id, p.referral_code, p.created_at as participant_created,
            p.browser, p.browser_version, p.os,
            p.screen_width, p.screen_height, p.pixel_ratio, p.color_depth,
            d.email, d.data as demographics_data,
            s.image_pair_id, s.stimulus_data, s.responses,
            s.was_randomized, s.time_spent, s.timing_flag, s.created_at as response_created
        '''

# Shared by the audited count and the stream, so the number logged is the number that ships.
_EXPORT_FROM = '''
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        JOIN survey_responses s ON p.id = s.participant_id
        '''

# The dashboard page reads the same row the export streams: one SELECT list, one join, no second copy to drift.
_ADMIN_RESULTS_SELECT = 'SELECT' + _EXPORT_SELECT + _EXPORT_FROM


def _export_fieldnames():
    """The CSV's columns, from the config: a stream has to name its header before it reads a row."""
    keys = set(_EXPORT_COLUMNS)
    keys.update(f"input_{inp['name']}" for inp in CONFIG['inputs'])
    keys.update(field['name'] for field in CONFIG['demographics'])
    for question in CONFIG['questions']:
        name = question['name']
        if question['type'] == 'ab_preference':
            keys.update({f'{name}_choice', f'{name}_confidence', f'{name}_preferred_method'})
        else:
            keys.add(f"{name}_{'text' if question['type'] == 'free_text' else 'value'}")
    return sorted(keys)


def _stream_csv(fieldnames):
    """One joined row per CSV line: the study used to sit in memory twice before the first byte."""
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction='ignore')
    db = get_db()

    def drain():
        chunk = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return chunk

    try:
        writer.writeheader()
        yield drain()
        for row in db.execute(f'SELECT {_EXPORT_SELECT} {_EXPORT_FROM} ORDER BY p.id, s.image_pair_id'):
            writer.writerow({key: _csv_safe(value) for key, value in _flatten_result(row).items()})
            yield drain()
    finally:
        db.close()


@app.route('/api/admin/delete_by_email', methods=['POST'])
@require_admin
@limiter.limit("20 per hour", key_func=get_remote_address)
def delete_by_email():
    """Delete all records associated with an email address"""
    body = request.get_json(silent=True)  # A JSON body that is not an object carries no email.
    email = body.get('email') if isinstance(body, dict) else None

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
