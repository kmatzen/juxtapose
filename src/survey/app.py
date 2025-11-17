from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort
import sqlite3
import uuid
import os
from datetime import datetime, timedelta
import json
import random
from functools import wraps
import hashlib
import secrets
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

app = Flask(__name__)

# Security: Detect production environment
IS_PRODUCTION = os.path.exists('/data')  # Fly.io mounts persistent volume at /data

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
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change this in production
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'  # Set DEV_MODE=true for testing

# Layout Configuration: Order of tiles in the three-tile grid
# Options: 'AMB' (A, Mask, B) or 'MAB' (Mask, A, B)
TILE_LAYOUT = os.environ.get('TILE_LAYOUT', 'AMB').upper()  # Set TILE_LAYOUT=MAB for mask-first layout
if TILE_LAYOUT not in ['AMB', 'MAB']:
    print(f"WARNING: Invalid TILE_LAYOUT '{TILE_LAYOUT}'. Using default 'AMB'. Valid options: AMB, MAB")
    TILE_LAYOUT = 'AMB'

# Question Configuration: Enable/disable specific evaluation questions
ENABLE_PROMPT_QUESTION = os.environ.get('ENABLE_PROMPT_QUESTION', 'false').lower() == 'true'  # Set ENABLE_PROMPT_QUESTION=true to enable

# Security: Warn if weak admin password in production
if ADMIN_PASSWORD == 'admin123' and IS_PRODUCTION:
    print("WARNING: Using default admin password! Set ADMIN_PASSWORD environment variable!")

# Audit log file
AUDIT_LOG_FILE = '/data/audit.log' if IS_PRODUCTION else 'audit.log'

# Referral codes - Set valid codes via environment variable (comma-separated) or in code
# If empty, no referral code is required
REFERRAL_CODES_ENV = os.environ.get('REFERRAL_CODES', '')
REFERRAL_CODES = set(code.strip() for code in REFERRAL_CODES_ENV.split(',') if code.strip()) if REFERRAL_CODES_ENV else set()

# Or set them directly here:
if not REFERRAL_CODES:
    REFERRAL_CODES = {
        'ADOBE2025',
    }

# In dev mode, bypass referral code requirement
REQUIRE_REFERRAL = bool(REFERRAL_CODES) and not DEV_MODE

# Use /data for persistent storage on Fly.io, otherwise local directory
DATABASE = '/data/survey.db' if IS_PRODUCTION else 'survey.db'

# Image pairs configuration file
IMAGE_PAIRS_FILE = os.environ.get('IMAGE_PAIRS_FILE', 'image_pairs.txt')

def load_image_pairs():
    """Load image pairs from text file"""
    pairs = []
    pair_id = 1
    
    # Get the path relative to the app root (parent of src/)
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(base_path, IMAGE_PAIRS_FILE)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Split by tab
                parts = line.split('\t')
                
                # Expect exactly 7 fields: prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls
                if len(parts) != 7:
                    print(f"Warning: Line {line_num} has {len(parts)} fields (expected 7), skipping: {line[:50]}...")
                    continue
                
                prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls = parts
                
                pairs.append({
                    "id": pair_id,
                    "prompt": prompt.strip(),
                    "method_a": method_a.strip(),
                    "method_b": method_b.strip(),
                    "image_a_url": image_a_url.strip(),
                    "image_b_url": image_b_url.strip(),
                    "identity_urls": identity_urls.strip() if identity_urls else None,
                    "mask_url": mask_url.strip() if mask_url else None
                })
                pair_id += 1
        
        if not pairs:
            raise ValueError(f"No valid image pairs found in {IMAGE_PAIRS_FILE}")
        
        print(f"✓ Loaded {len(pairs)} image pairs from {IMAGE_PAIRS_FILE}")
        return pairs
        
    except FileNotFoundError:
        print(f"ERROR: {IMAGE_PAIRS_FILE} not found at {file_path}")
        print("Creating sample file with 3 placeholder pairs...")
        
        # Create a sample file with helpful instructions
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Image Pairs Configuration\n")
            f.write("# Format: prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url <TAB> mask_url <TAB> identity_urls\n")
            f.write("# mask_url: single spatial mask image\n")
            f.write("# identity_urls: single URL to stacked identity image (512px wide x 512N tall, N = number of identities)\n")
            f.write("# Lines starting with # are comments\n\n")
            f.write("A serene mountain landscape\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\thttps://placehold.co/300x300/yellow/black?text=Mask\thttps://placehold.co/200x200/gray/white?text=Identity\n")
            f.write("A futuristic city\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\thttps://placehold.co/300x300/yellow/black?text=Mask\thttps://placehold.co/200x200/gray/white?text=Identity\n")
            f.write("A person skiing\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\thttps://placehold.co/300x300/yellow/black?text=Mask\thttps://placehold.co/512x1024/gray/white?text=Stacked+IDs\n")
        
        print(f"✓ Created {file_path} with sample data")
        # Recursively call to load the newly created file
        return load_image_pairs()
    
    except Exception as e:
        print(f"ERROR loading {IMAGE_PAIRS_FILE}: {e}")
        raise

# Load image pairs on startup
IMAGE_PAIRS = load_image_pairs()

# Run database migrations before initializing
try:
    from src.survey.migrate_db import migrate_database
    migrate_database()
except Exception as e:
    print(f"Warning: Migration failed (might be first run): {e}")

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
        print(f"Audit logging error: {e}")

# Security: HTTP Security Headers
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Only set HSTS in production (Fly.io handles HTTPS)
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

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
            occupation TEXT,
            has_used_image_gen TEXT,
            image_gen_tools TEXT,
            works_on_ai_development TEXT,
            ai_usage_frequency TEXT,
            works_with_graphics TEXT,
            technical_background TEXT,
            ai_familiarity TEXT,
            other_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            image_pair_id INTEGER,
            prompt TEXT,
            method_a TEXT,
            method_b TEXT,
            image_a_url TEXT,
            image_b_url TEXT,
            identity_urls TEXT,
            mask_url TEXT,
            better_image TEXT,
            image_confidence INTEGER,
            better_prompt_match TEXT,
            prompt_confidence INTEGER,
            better_mask_match TEXT,
            mask_confidence INTEGER,
            better_identity_match TEXT,
            identity_confidence INTEGER,
            was_randomized INTEGER DEFAULT 0,
            time_spent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')
    
    # Add time_spent column if it doesn't exist (for existing databases)
    try:
        db.execute('ALTER TABLE survey_responses ADD COLUMN time_spent REAL')
    except:
        pass  # Column already exists
    
    db.commit()
    db.close()

# Initialize database on startup
init_db()

# Health check endpoint (must come after init)
@app.route('/health')
def health():
    """Simple health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'pairs_loaded': len(IMAGE_PAIRS),
        'dev_mode': DEV_MODE,
        'database': DATABASE
    }), 200

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

@app.route('/')
def index():
    """Home page - check referral code and if user has already submitted"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Check if referral code is required and validated
    if REQUIRE_REFERRAL and not session.get('referral_validated'):
        return redirect(url_for('referral'))
    
    # Check for explicit "new" parameter to force restart in dev mode
    force_new = request.args.get('new') == 'true'
    
    # Check if this session has completed the survey
    db = get_db()
    participant = db.execute(
        'SELECT id FROM participants WHERE session_id = ?',
        (session['session_id'],)
    ).fetchone()
    
    if participant:
        # Get user's email to check for completed pairs
        demo = db.execute(
            'SELECT email FROM demographics WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        db.close()
        
        if demo and demo['email']:
            # Check how many pairs they've completed (fully answered)
            completed_pair_ids = get_completed_pair_ids_for_email(demo['email'])
            # Check how many pairs are available total
            total_available_pairs = len(IMAGE_PAIRS)
            # In dev mode, limit to 3; in prod, limit to 30
            max_pairs = 3 if DEV_MODE else 30
            expected_pairs = min(total_available_pairs, max_pairs)
            
            print(f"[DEBUG] Index route check: email={demo['email']}, completed={len(completed_pair_ids)}, expected={expected_pairs}, tutorial_complete={session.get('tutorial_completed', False)}")
            
            # If they've completed all available pairs (or reached the limit), show thank you
            if len(completed_pair_ids) >= expected_pairs:
                # In dev mode, allow restarting with ?new=true parameter
                if DEV_MODE and force_new:
                    print(f"[DEBUG] Showing survey (force_new)")
                    return render_template('index.html', tile_layout=TILE_LAYOUT, enable_prompt_question=ENABLE_PROMPT_QUESTION)
                # Show thank you page if completed
                print(f"[DEBUG] Showing thank you page (survey complete)")
                return render_template('thank_you.html', already_submitted=True, dev_mode=DEV_MODE)
            
            # Demographics completed, check if tutorial completed
            if not session.get('tutorial_completed', False):
                print(f"[DEBUG] Redirecting to tutorial")
                return redirect(url_for('tutorial'))
    else:
        db.close()
    
    return render_template('index.html', tile_layout=TILE_LAYOUT, enable_prompt_question=ENABLE_PROMPT_QUESTION)

@app.route('/referral', methods=['GET', 'POST'])
def referral():
    """Referral code entry page"""
    if not REQUIRE_REFERRAL:
        # If no referral code required, skip to survey
        session['referral_validated'] = True
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        code = request.form.get('referral_code', '').strip().upper()
        
        if code in REFERRAL_CODES:
            session['referral_validated'] = True
            session['referral_code'] = code
            return redirect(url_for('index'))
        else:
            return render_template('referral.html', error='Invalid referral code. Please check and try again.')
    
    return render_template('referral.html')

@app.route('/reset_session')
def reset_session():
    """Reset session - useful for dev/testing or shared computers"""
    if DEV_MODE:
        session.clear()
        return redirect(url_for('referral') if REQUIRE_REFERRAL else url_for('index'))
    else:
        # In production, show styled confirmation page
        return render_template('reset_session_confirm.html')

@app.route('/reset_session_confirm', methods=['POST'])
def reset_session_confirm():
    """Confirm session reset"""
    session.clear()
    return redirect(url_for('referral') if REQUIRE_REFERRAL else url_for('index'))

@app.route('/tutorial')
def tutorial():
    """Show tutorial mode - interactive walkthrough using real survey interface"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Check if user should be here
    if not session.get('referral_validated', False):
        return redirect(url_for('referral'))
    
    # Check if demographics completed
    demographics_completed = False
    if 'session_id' in session:
        conn = get_db()
        c = conn.cursor()
        # Join participants and demographics tables using session_id
        c.execute('''
            SELECT d.id FROM demographics d
            JOIN participants p ON d.participant_id = p.id
            WHERE p.session_id = ?
        ''', (session['session_id'],))
        demographics_completed = c.fetchone() is not None
        conn.close()
    
    if not demographics_completed:
        return redirect(url_for('index'))
    
    # Render the survey page in tutorial mode
    return render_template('index.html', tile_layout=TILE_LAYOUT, enable_prompt_question=ENABLE_PROMPT_QUESTION, tutorial_mode=True)

@app.route('/api/complete_tutorial', methods=['POST'])
@csrf.exempt  # Exempt from CSRF - protected by session
def complete_tutorial():
    """Mark tutorial as completed"""
    if 'session_id' not in session:
        return jsonify({'error': 'No session'}), 400
    
    session['tutorial_completed'] = True
    return jsonify({'ok': True})

@app.route('/api/config')
def get_config():
    """Get configuration settings for frontend"""
    return jsonify({
        'dev_mode': DEV_MODE
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
        
        # Get how many pairs have been completed
        completed_count = db.execute('''
            SELECT COUNT(*) as count FROM survey_responses 
            WHERE participant_id = ?
                AND better_image IS NOT NULL
                AND image_confidence IS NOT NULL
                AND better_prompt_match IS NOT NULL
                AND prompt_confidence IS NOT NULL
                AND better_mask_match IS NOT NULL
                AND mask_confidence IS NOT NULL
                AND better_identity_match IS NOT NULL
                AND identity_confidence IS NOT NULL
        ''', (participant['id'],)).fetchone()
        
        return jsonify({
            'submitted': True,
            'completed_pairs': completed_count['count'] if completed_count else 0
        })
    finally:
        db.close()

@app.route('/api/submit_demographics', methods=['POST'])
@csrf.exempt  # Exempt from CSRF - protected by session
def submit_demographics():
    """Submit demographics information"""
    if 'session_id' not in session:
        return jsonify({'error': 'No session ID'}), 400
    
    data = request.json
    db = get_db()
    
    try:
        # Check if this email has been used before (detect retakes by email, not session)
        email = data.get('email')
        is_retaking = False
        
        if email:
            # Look for previous submissions with this email
            previous_participant = db.execute('''
                SELECT p.id 
                FROM participants p
                JOIN demographics d ON p.id = d.participant_id
                WHERE d.email = ?
                LIMIT 1
            ''', (email,)).fetchone()
            
            if previous_participant:
                # Check if they have any survey responses
                response_count = db.execute(
                    'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
                    (previous_participant['id'],)
                ).fetchone()
                is_retaking = response_count and response_count['count'] > 0
                
                # If retaking, clear all previous data for this email to start fresh
                if is_retaking:
                    # Delete all responses for all participants with this email
                    db.execute('''
                        DELETE FROM survey_responses 
                        WHERE participant_id IN (
                            SELECT p.id FROM participants p
                            JOIN demographics d ON p.id = d.participant_id
                            WHERE d.email = ?
                        )
                    ''', (email,))
                    
                    # Delete all demographics for this email
                    db.execute('DELETE FROM demographics WHERE email = ?', (email,))
        
        # Create or get participant for current session
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()
        
        if not participant:
            # Extract device info
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
                device_info.get('viewport_height')
            ))
            participant_id = cursor.lastrowid
        else:
            participant_id = participant['id']
        
        # Store demographics
        db.execute('''
            INSERT INTO demographics 
            (participant_id, email, occupation, has_used_image_gen, image_gen_tools,
             works_on_ai_development, ai_usage_frequency, works_with_graphics,
             technical_background, ai_familiarity, other_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            participant_id,
            data.get('email'),
            data.get('occupation'),
            data.get('has_used_image_gen'),
            data.get('image_gen_tools'),
            data.get('works_on_ai_development'),
            data.get('ai_usage_frequency'),
            data.get('works_with_graphics'),
            data.get('technical_background'),
            data.get('ai_familiarity'),
            json.dumps(data.get('other', {}))
        ))
        
        db.commit()
        return jsonify({
            'success': True, 
            'participant_id': participant_id,
            'is_retaking': is_retaking
        })
    except Exception as e:
        db.rollback()
        # Security: Don't leak internal error details
        print(f"Error in submit_demographics: {e}")
        return jsonify({'error': 'An error occurred while submitting demographics'}), 500
    finally:
        db.close()

def get_completed_pair_ids_for_email(email):
    """Get list of pair IDs that have been fully completed by this email address.
    A pair is considered complete only if all 8 questions have been answered
    (4 choice questions + 4 confidence questions)."""
    if not email:
        return []
    
    db = get_db()
    try:
        # Get all participant IDs for this email
        participant_ids = db.execute('''
            SELECT p.id 
            FROM participants p
            JOIN demographics d ON p.id = d.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchall()
        
        if not participant_ids:
            return []
        
        participant_id_list = [p['id'] for p in participant_ids]
        
        # Get image_pair_ids where required fields are non-null
        # Base requirements: better_image, image_confidence, mask, identity
        # Conditional: prompt match/confidence only if enabled
        placeholders = ','.join('?' * len(participant_id_list))
        
        # Build query based on enabled questions
        query = f'''
            SELECT image_pair_id
            FROM survey_responses
            WHERE participant_id IN ({placeholders})
                AND better_image IS NOT NULL
                AND image_confidence IS NOT NULL
                AND better_mask_match IS NOT NULL
                AND mask_confidence IS NOT NULL
                AND better_identity_match IS NOT NULL
                AND identity_confidence IS NOT NULL
        '''
        
        # Only require prompt fields if the prompt question is enabled
        if ENABLE_PROMPT_QUESTION:
            query += '''
                AND better_prompt_match IS NOT NULL
                AND prompt_confidence IS NOT NULL
            '''
        
        completed_pairs = db.execute(query, participant_id_list).fetchall()
        
        return [row['image_pair_id'] for row in completed_pairs]
    finally:
        db.close()

@app.route('/api/get_image_pair/<int:pair_index>')
def get_image_pair(pair_index):
    """Get a specific image pair"""
    # Initialize user's randomized pair list if not already done
    # OR if DEV_MODE has changed since session was created
    if 'user_image_pairs' not in session or session.get('session_dev_mode') != DEV_MODE:
        # Get the user's email from demographics (if they've submitted it)
        user_email = None
        if 'session_id' in session:
            db = get_db()
            try:
                demo = db.execute('''
                    SELECT d.email 
                    FROM demographics d
                    JOIN participants p ON d.participant_id = p.id
                    WHERE p.session_id = ?
                    ORDER BY d.id DESC
                    LIMIT 1
                ''', (session['session_id'],)).fetchone()
                if demo:
                    user_email = demo['email']
            finally:
                db.close()
        
        # Get list of completed pair IDs for this email
        completed_pair_ids = get_completed_pair_ids_for_email(user_email) if user_email else []
        
        # Filter out completed pairs from available pairs
        available_pairs = [p for p in IMAGE_PAIRS if p['id'] not in completed_pair_ids]
        
        # In dev mode, use first 3 pairs; in production, randomly sample up to 30
        max_pairs = 3 if DEV_MODE else 30
        
        # If we have fewer pairs than max, use all of them
        num_pairs = min(len(available_pairs), max_pairs)
        
        # Randomly sample and shuffle pairs for this user
        if len(available_pairs) <= num_pairs:
            # Use all available pairs, but in random order
            user_pairs = available_pairs.copy()
            random.shuffle(user_pairs)
        else:
            # Randomly sample without replacement
            user_pairs = random.sample(available_pairs, num_pairs)
        
        # Store the shuffled pair list in session (store just the IDs to keep session small)
        session['user_image_pairs'] = [pair['id'] for pair in user_pairs]
        session['user_pairs_count'] = len(user_pairs)
        session['session_dev_mode'] = DEV_MODE  # Track which mode this session was created in
    
    # Get user's pair list
    user_pair_ids = session.get('user_image_pairs', [])
    
    if pair_index < 0 or pair_index >= len(user_pair_ids):
        return jsonify({'error': 'Invalid image pair index'}), 404
    
    # Find the actual pair by ID
    pair_id = user_pair_ids[pair_index]
    pair = next((p for p in IMAGE_PAIRS if p['id'] == pair_id), None)
    
    if not pair:
        return jsonify({'error': 'Image pair not found'}), 404
    
    pair = pair.copy()
    
    # ALWAYS randomize A/B position to prevent position bias
    randomized = random.random() < 0.5
    if randomized:
        # Swap the images AND the method names
        pair['image_a_url'], pair['image_b_url'] = pair['image_b_url'], pair['image_a_url']
        pair['method_a'], pair['method_b'] = pair['method_b'], pair['method_a']
    
    pair['was_randomized'] = randomized
    pair['total_pairs'] = len(user_pair_ids)
    return jsonify(pair)

@app.route('/api/submit_survey', methods=['POST'])
@csrf.exempt  # Exempt from CSRF - protected by session
def submit_survey():
    """Submit survey response for a single image pair"""
    if 'session_id' not in session:
        return jsonify({'error': 'No session ID'}), 400
    
    data = request.json
    db = get_db()
    
    try:
        # Get participant
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()
        
        if not participant:
            return jsonify({'error': 'Participant not found'}), 404
        
        # Check if this specific image pair was already answered
        existing = db.execute(
            'SELECT id FROM survey_responses WHERE participant_id = ? AND image_pair_id = ?',
            (participant['id'], data.get('image_pair_id'))
        ).fetchone()
        
        if existing:
            # Update existing response (allow retaking)
            db.execute('''
                UPDATE survey_responses 
                SET prompt = ?, 
                    method_a = ?,
                    method_b = ?,
                    image_a_url = ?, 
                    image_b_url = ?,
                    identity_urls = ?,
                    mask_url = ?,
                    better_image = ?, 
                    image_confidence = ?, 
                    better_prompt_match = ?, 
                    prompt_confidence = ?,
                    better_mask_match = ?,
                    mask_confidence = ?,
                    better_identity_match = ?,
                    identity_confidence = ?,
                    was_randomized = ?,
                    time_spent = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('prompt'),
                data.get('method_a'),
                data.get('method_b'),
                data.get('image_a_url'),
                data.get('image_b_url'),
                data.get('identity_urls'),
                data.get('mask_url'),
                data.get('better_image'),
                data.get('image_confidence'),
                data.get('better_prompt_match'),
                data.get('prompt_confidence'),
                data.get('better_mask_match'),
                data.get('mask_confidence'),
                data.get('better_identity_match'),
                data.get('identity_confidence'),
                1 if data.get('was_randomized') else 0,
                data.get('time_spent'),
                existing['id']
            ))
        else:
            # Insert new response
            db.execute('''
                INSERT INTO survey_responses 
                (participant_id, image_pair_id, prompt, method_a, method_b, image_a_url, image_b_url,
                 identity_urls, mask_url,
                 better_image, image_confidence, better_prompt_match, prompt_confidence,
                 better_mask_match, mask_confidence, better_identity_match, identity_confidence,
                 was_randomized, time_spent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                participant['id'],
                data.get('image_pair_id'),
                data.get('prompt'),
                data.get('method_a'),
                data.get('method_b'),
                data.get('image_a_url'),
                data.get('image_b_url'),
                data.get('identity_urls'),
                data.get('mask_url'),
                data.get('better_image'),
                data.get('image_confidence'),
                data.get('better_prompt_match'),
                data.get('prompt_confidence'),
                data.get('better_mask_match'),
                data.get('mask_confidence'),
                data.get('better_identity_match'),
                data.get('identity_confidence'),
                1 if data.get('was_randomized') else 0,
                data.get('time_spent')
            ))
        
        # Check if they've completed all their assigned image pairs
        user_pairs_count = session.get('user_pairs_count', min(len(IMAGE_PAIRS), 30 if not DEV_MODE else 3))
        
        db.commit()
        
        # Get user's email to check completed pairs
        demo = db.execute(
            'SELECT email FROM demographics WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        
        if demo and demo['email']:
            completed_pair_ids = get_completed_pair_ids_for_email(demo['email'])
            completed = len(completed_pair_ids) >= user_pairs_count
            print(f"[DEBUG] Submit check: email={demo['email']}, completed_pairs={len(completed_pair_ids)}, user_pairs_count={user_pairs_count}, completed={completed}")
        else:
            completed = False
        
        return jsonify({'success': True, 'completed': completed})
    except Exception as e:
        db.rollback()
        # Security: Don't leak internal error details
        print(f"Error in submit_survey: {e}")
        return jsonify({'error': 'An error occurred while submitting survey response'}), 500
    finally:
        db.close()

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")  # Security: Strict rate limit on login attempts
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        ip = get_remote_address()
        
        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            session.permanent = True  # Enable 2-hour timeout for admin sessions
            
            # Security: Audit successful login
            audit_log('ADMIN_LOGIN_SUCCESS', {'ip': ip})
            
            return redirect(url_for('admin'))
        else:
            # Security: Audit failed login attempt
            audit_log('ADMIN_LOGIN_FAILED', {'ip': ip, 'reason': 'Invalid password'})
            
            # Security: Don't reveal whether username or password was wrong
            return render_template('admin_login.html', error='Invalid credentials'), 401
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    if session.get('admin_authenticated'):
        # Security: Audit logout
        audit_log('ADMIN_LOGOUT', {'ip': get_remote_address()})
    
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@require_admin
def admin():
    """Admin page to view results"""
    return render_template('admin.html')

@app.route('/api/admin/results')
@require_admin
def admin_results():
    """Get all survey results"""
    db = get_db()
    
    results = db.execute('''
        SELECT 
            p.session_id,
            p.referral_code,
            p.created_at as participant_created,
            p.browser,
            p.browser_version,
            p.os,
            p.screen_width,
            p.screen_height,
            p.pixel_ratio,
            p.color_depth,
            d.email,
            d.occupation,
            d.has_used_image_gen,
            d.image_gen_tools,
            d.works_on_ai_development,
            d.ai_usage_frequency,
            d.works_with_graphics,
            d.technical_background,
            d.ai_familiarity,
            s.image_pair_id,
            s.prompt,
            s.method_a,
            s.method_b,
            s.image_a_url,
            s.image_b_url,
            s.identity_urls,
            s.mask_url,
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.better_mask_match,
            s.mask_confidence,
            s.better_identity_match,
            s.identity_confidence,
            s.was_randomized,
            s.time_spent,
            s.created_at as response_created,
            CASE 
                WHEN s.better_image = 'A' THEN s.method_a
                WHEN s.better_image = 'B' THEN s.method_b
                WHEN s.better_image = 'equal' THEN 'equal'
            END as preferred_method_image,
            CASE 
                WHEN s.better_prompt_match = 'A' THEN s.method_a
                WHEN s.better_prompt_match = 'B' THEN s.method_b
                WHEN s.better_prompt_match = 'equal' THEN 'equal'
            END as preferred_method_prompt,
            CASE 
                WHEN s.better_mask_match = 'A' THEN s.method_a
                WHEN s.better_mask_match = 'B' THEN s.method_b
                WHEN s.better_mask_match = 'equal' THEN 'equal'
            END as preferred_method_mask,
            CASE 
                WHEN s.better_identity_match = 'A' THEN s.method_a
                WHEN s.better_identity_match = 'B' THEN s.method_b
                WHEN s.better_identity_match = 'equal' THEN 'equal'
            END as preferred_method_identity
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        LEFT JOIN survey_responses s ON p.id = s.participant_id
        WHERE s.id IS NOT NULL
        ORDER BY s.created_at DESC
    ''').fetchall()
    
    db.close()
    
    return jsonify([dict(row) for row in results])

@app.route('/api/admin/export')
@require_admin
def admin_export():
    """Export results as CSV"""
    import csv
    from io import StringIO
    
    db = get_db()
    results = db.execute('''
        SELECT 
            p.session_id,
            p.referral_code,
            p.created_at as participant_created,
            p.browser,
            p.browser_version,
            p.os,
            p.screen_width,
            p.screen_height,
            p.pixel_ratio,
            p.color_depth,
            d.email,
            d.occupation,
            d.has_used_image_gen,
            d.image_gen_tools,
            d.works_on_ai_development,
            d.ai_usage_frequency,
            d.works_with_graphics,
            d.technical_background,
            d.ai_familiarity,
            s.image_pair_id,
            s.prompt,
            s.method_a,
            s.method_b,
            s.image_a_url,
            s.image_b_url,
            s.identity_urls,
            s.mask_url,
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.better_mask_match,
            s.mask_confidence,
            s.better_identity_match,
            s.identity_confidence,
            s.was_randomized,
            s.time_spent,
            s.created_at as response_created,
            CASE 
                WHEN s.better_image = 'A' THEN s.method_a
                WHEN s.better_image = 'B' THEN s.method_b
                WHEN s.better_image = 'equal' THEN 'equal'
            END as preferred_method_image,
            CASE 
                WHEN s.better_prompt_match = 'A' THEN s.method_a
                WHEN s.better_prompt_match = 'B' THEN s.method_b
                WHEN s.better_prompt_match = 'equal' THEN 'equal'
            END as preferred_method_prompt,
            CASE 
                WHEN s.better_mask_match = 'A' THEN s.method_a
                WHEN s.better_mask_match = 'B' THEN s.method_b
                WHEN s.better_mask_match = 'equal' THEN 'equal'
            END as preferred_method_mask,
            CASE 
                WHEN s.better_identity_match = 'A' THEN s.method_a
                WHEN s.better_identity_match = 'B' THEN s.method_b
                WHEN s.better_identity_match = 'equal' THEN 'equal'
            END as preferred_method_identity
        FROM participants p
        LEFT JOIN demographics d ON p.id = d.participant_id
        LEFT JOIN survey_responses s ON p.id = s.participant_id
        WHERE s.id IS NOT NULL
        ORDER BY p.id, s.image_pair_id
    ''').fetchall()
    db.close()
    
    output = StringIO()
    if results:
        writer = csv.DictWriter(output, fieldnames=results[0].keys())
        writer.writeheader()
        for row in results:
            writer.writerow(dict(row))
    
    response = app.response_class(
        response=output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=survey_results.csv'}
    )
    return response

@app.route('/api/admin/delete_by_email', methods=['POST'])
@require_admin
@limiter.limit("20 per hour")  # Security: Rate limit delete operations
def delete_by_email():
    """Delete all records associated with an email address"""
    email = request.json.get('email') if request.json else None
    
    # Security: Input validation
    if not email:
        audit_log('DELETE_FAILED', {'reason': 'No email provided'})
        return jsonify({'error': 'Email address is required'}), 400
    
    # Security: Basic email format validation
    if '@' not in email or len(email) > 255:
        audit_log('DELETE_FAILED', {'reason': 'Invalid email format', 'email': email[:50]})
        return jsonify({'error': 'Invalid email format'}), 400
    
    db = get_db()
    try:
        # Find all participant IDs associated with this email
        participant_ids = db.execute('''
            SELECT p.id 
            FROM participants p
            JOIN demographics d ON p.id = d.participant_id
            WHERE d.email = ?
        ''', (email,)).fetchall()
        
        if not participant_ids:
            # Security: Audit attempted deletion of non-existent email
            audit_log('DELETE_NOT_FOUND', {'email': email})
            return jsonify({'error': 'No records found for this email address'}), 404
        
        participant_id_list = [p['id'] for p in participant_ids]
        placeholders = ','.join('?' * len(participant_id_list))
        
        # Delete survey responses
        responses_deleted = db.execute(
            f'DELETE FROM survey_responses WHERE participant_id IN ({placeholders})',
            participant_id_list
        ).rowcount
        
        # Delete demographics
        demographics_deleted = db.execute(
            f'DELETE FROM demographics WHERE participant_id IN ({placeholders})',
            participant_id_list
        ).rowcount
        
        # Delete participants
        participants_deleted = db.execute(
            f'DELETE FROM participants WHERE id IN ({placeholders})',
            participant_id_list
        ).rowcount
        
        db.commit()
        
        # Security: Audit successful deletion
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
        # Security: Audit deletion error, but don't leak details to client
        audit_log('DELETE_ERROR', {'email': email, 'error': str(e)})
        return jsonify({'error': 'An error occurred while deleting records'}), 500
    finally:
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

