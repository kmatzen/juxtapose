from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import uuid
import os
from datetime import datetime
import json
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change this in production
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'  # Set DEV_MODE=true for testing

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
DATABASE = '/data/survey.db' if os.path.exists('/data') else 'survey.db'

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
                if len(parts) != 5:
                    print(f"Warning: Line {line_num} has {len(parts)} fields (expected 5), skipping: {line[:50]}...")
                    continue
                
                prompt, method_a, method_b, image_a_url, image_b_url = parts
                
                pairs.append({
                    "id": pair_id,
                    "prompt": prompt.strip(),
                    "method_a": method_a.strip(),
                    "method_b": method_b.strip(),
                    "image_a_url": image_a_url.strip(),
                    "image_b_url": image_b_url.strip()
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
            f.write("# Format: prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url\n")
            f.write("# Lines starting with # are comments and will be ignored\n\n")
            f.write("A serene mountain landscape at sunset\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\n")
            f.write("A futuristic city with flying cars\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\n")
            f.write("A cat wearing sunglasses on a beach\tMethod-A\tMethod-B\thttps://placehold.co/600x400/0066cc/white?text=Method+A\thttps://placehold.co/600x400/cc6600/white?text=Method+B\n")
        
        print(f"✓ Created {file_path} with sample data")
        # Recursively call to load the newly created file
        return load_image_pairs()
    
    except Exception as e:
        print(f"ERROR loading {IMAGE_PAIRS_FILE}: {e}")
        raise

# Load image pairs on startup
IMAGE_PAIRS = load_image_pairs()

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
            better_image TEXT,
            image_confidence INTEGER,
            better_prompt_match TEXT,
            prompt_confidence INTEGER,
            was_randomized INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')
    
    db.commit()
    db.close()

# Initialize database on startup
init_db()

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
        # Get the number of pairs assigned to this user (from session or default)
        user_pairs_count = session.get('user_pairs_count', min(len(IMAGE_PAIRS), 30 if not DEV_MODE else 3))
        
        # Check if they've completed all their assigned questions
        response_count = db.execute(
            'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        db.close()
        
        if response_count and response_count['count'] >= user_pairs_count:
            # In dev mode, allow restarting with ?new=true parameter
            if DEV_MODE and force_new:
                return render_template('index.html')
            # Show thank you page if completed
            return render_template('thank_you.html', already_submitted=True, dev_mode=DEV_MODE)
    else:
        db.close()
    
    return render_template('index.html')

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

@app.route('/api/config')
def get_config():
    """Get configuration settings for frontend"""
    return jsonify({
        'dev_mode': DEV_MODE
    })

@app.route('/api/submit_demographics', methods=['POST'])
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
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/get_image_pair/<int:pair_index>')
def get_image_pair(pair_index):
    """Get a specific image pair"""
    # Initialize user's randomized pair list if not already done
    if 'user_image_pairs' not in session:
        # In dev mode, use first 3 pairs; in production, randomly sample up to 30
        max_pairs = 3 if DEV_MODE else 30
        
        # If we have fewer pairs than max, use all of them
        num_pairs = min(len(IMAGE_PAIRS), max_pairs)
        
        # Randomly sample and shuffle pairs for this user
        if len(IMAGE_PAIRS) <= num_pairs:
            # Use all pairs, but in random order
            user_pairs = IMAGE_PAIRS.copy()
            random.shuffle(user_pairs)
        else:
            # Randomly sample without replacement
            user_pairs = random.sample(IMAGE_PAIRS, num_pairs)
        
        # Store the shuffled pair list in session (store just the IDs to keep session small)
        session['user_image_pairs'] = [pair['id'] for pair in user_pairs]
        session['user_pairs_count'] = len(user_pairs)
    
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
                    better_image = ?, 
                    image_confidence = ?, 
                    better_prompt_match = ?, 
                    prompt_confidence = ?, 
                    was_randomized = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('prompt'),
                data.get('method_a'),
                data.get('method_b'),
                data.get('image_a_url'),
                data.get('image_b_url'),
                data.get('better_image'),
                data.get('image_confidence'),
                data.get('better_prompt_match'),
                data.get('prompt_confidence'),
                1 if data.get('was_randomized') else 0,
                existing['id']
            ))
        else:
            # Insert new response
            db.execute('''
                INSERT INTO survey_responses 
                (participant_id, image_pair_id, prompt, method_a, method_b, image_a_url, image_b_url,
                 better_image, image_confidence, better_prompt_match, prompt_confidence, was_randomized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                participant['id'],
                data.get('image_pair_id'),
                data.get('prompt'),
                data.get('method_a'),
                data.get('method_b'),
                data.get('image_a_url'),
                data.get('image_b_url'),
                data.get('better_image'),
                data.get('image_confidence'),
                data.get('better_prompt_match'),
                data.get('prompt_confidence'),
                1 if data.get('was_randomized') else 0
            ))
        
        # Check if they've completed all their assigned image pairs
        user_pairs_count = session.get('user_pairs_count', min(len(IMAGE_PAIRS), 30 if not DEV_MODE else 3))
        response_count = db.execute(
            'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        
        db.commit()
        
        completed = response_count['count'] >= user_pairs_count
        return jsonify({'success': True, 'completed': completed})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error='Invalid password')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
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
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.was_randomized,
            s.created_at as response_created,
            CASE 
                WHEN s.better_image = 'A' THEN s.method_a
                WHEN s.better_image = 'B' THEN s.method_b
            END as preferred_method_image,
            CASE 
                WHEN s.better_prompt_match = 'A' THEN s.method_a
                WHEN s.better_prompt_match = 'B' THEN s.method_b
            END as preferred_method_prompt
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
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.was_randomized,
            s.created_at as response_created,
            CASE 
                WHEN s.better_image = 'A' THEN s.method_a
                WHEN s.better_image = 'B' THEN s.method_b
            END as preferred_method_image,
            CASE 
                WHEN s.better_prompt_match = 'A' THEN s.method_a
                WHEN s.better_prompt_match = 'B' THEN s.method_b
            END as preferred_method_prompt
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

