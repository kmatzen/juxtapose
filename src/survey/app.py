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

# Use /data for persistent storage on Fly.io, otherwise local directory
DATABASE = '/data/survey.db' if os.path.exists('/data') else 'survey.db'

# Image pairs - customize these with your actual images and prompts
IMAGE_PAIRS = [
    {
        "id": 1,
        "prompt": "A serene mountain landscape at sunset",
        "image_a_url": "https://placehold.co/600x400/0066cc/white?text=Image+A-1",
        "image_b_url": "https://placehold.co/600x400/cc6600/white?text=Image+B-1"
    },
    {
        "id": 2,
        "prompt": "A futuristic city with flying cars",
        "image_a_url": "https://placehold.co/600x400/0066cc/white?text=Image+A-2",
        "image_b_url": "https://placehold.co/600x400/cc6600/white?text=Image+B-2"
    },
    # Add 28 more image pairs here
    # Template for adding more:
    # {
    #     "id": 3,
    #     "prompt": "Your text prompt here",
    #     "image_a_url": "URL or path to image A",
    #     "image_b_url": "URL or path to image B"
    # },
]

# Generate placeholder image pairs if we don't have 30 yet
while len(IMAGE_PAIRS) < 30:
    idx = len(IMAGE_PAIRS) + 1
    IMAGE_PAIRS.append({
        "id": idx,
        "prompt": f"Sample prompt #{idx} - Replace this with your actual image generation prompt.",
        "image_a_url": f"https://placehold.co/600x400/0066cc/white?text=Image+A-{idx}",
        "image_b_url": f"https://placehold.co/600x400/cc6600/white?text=Image+B-{idx}"
    })

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
    """Home page - check if user has already submitted"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # In dev mode, use fewer image pairs
    required_count = 3 if DEV_MODE else 30
    
    # Skip completion check in dev mode to allow re-testing
    if not DEV_MODE:
        # Check if this session has already submitted
        db = get_db()
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()
        
        if participant:
            # Check if they've completed all required questions
            response_count = db.execute(
                'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
                (participant['id'],)
            ).fetchone()
            db.close()
            
            if response_count and response_count['count'] >= required_count:
                return render_template('thank_you.html', already_submitted=True)
        else:
            db.close()
    
    return render_template('index.html')

@app.route('/reset_session')
def reset_session():
    """Reset session - useful for dev/testing or shared computers"""
    if DEV_MODE:
        session.clear()
        return redirect(url_for('index'))
    else:
        # In production, require confirmation
        return '''
            <html>
            <head><title>Reset Session</title></head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h2>Reset Survey Session</h2>
                <p>This will clear your session and allow you to take the survey again.</p>
                <p style="color: #d32f2f;"><strong>Note:</strong> This is intended for shared computers. 
                Your previous responses will remain in the database.</p>
                <form method="POST" action="/reset_session_confirm" style="margin-top: 20px;">
                    <button type="submit" style="padding: 10px 20px; font-size: 16px; cursor: pointer;">
                        Yes, Reset My Session
                    </button>
                    <br><br>
                    <a href="/" style="color: #666;">Cancel and return to survey</a>
                </form>
            </body>
            </html>
        '''

@app.route('/reset_session_confirm', methods=['POST'])
def reset_session_confirm():
    """Confirm session reset"""
    session.clear()
    return redirect(url_for('index'))

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
        # Create or get participant
        participant = db.execute(
            'SELECT id FROM participants WHERE session_id = ?',
            (session['session_id'],)
        ).fetchone()
        
        # Check if they're retaking the survey
        is_retaking = False
        if participant:
            response_count = db.execute(
                'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
                (participant['id'],)
            ).fetchone()
            is_retaking = response_count and response_count['count'] > 0
        
        if not participant:
            # Extract device info
            device_info = data.get('device_info', {})
            cursor = db.execute('''
                INSERT INTO participants 
                (session_id, browser, browser_version, os, screen_width, screen_height,
                 pixel_ratio, color_depth, viewport_width, viewport_height)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['session_id'],
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
    # In dev mode, only use first 3 image pairs
    available_pairs = IMAGE_PAIRS[:3] if DEV_MODE else IMAGE_PAIRS
    
    if pair_index < 0 or pair_index >= len(available_pairs):
        return jsonify({'error': 'Invalid image pair index'}), 404
    
    pair = available_pairs[pair_index].copy()
    
    # Randomize the order 50% of the time
    randomized = random.random() < 0.5
    if randomized:
        pair['image_a_url'], pair['image_b_url'] = pair['image_b_url'], pair['image_a_url']
    
    pair['was_randomized'] = randomized
    pair['total_pairs'] = len(available_pairs)
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
                (participant_id, image_pair_id, prompt, image_a_url, image_b_url,
                 better_image, image_confidence, better_prompt_match, prompt_confidence, was_randomized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                participant['id'],
                data.get('image_pair_id'),
                data.get('prompt'),
                data.get('image_a_url'),
                data.get('image_b_url'),
                data.get('better_image'),
                data.get('image_confidence'),
                data.get('better_prompt_match'),
                data.get('prompt_confidence'),
                1 if data.get('was_randomized') else 0
            ))
        
        # Check if they've completed all image pairs
        required_count = 3 if DEV_MODE else 30
        response_count = db.execute(
            'SELECT COUNT(*) as count FROM survey_responses WHERE participant_id = ?',
            (participant['id'],)
        ).fetchone()
        
        db.commit()
        
        completed = response_count['count'] >= required_count
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
            s.image_a_url,
            s.image_b_url,
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.was_randomized,
            s.created_at as response_created
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
            s.image_a_url,
            s.image_b_url,
            s.better_image,
            s.image_confidence,
            s.better_prompt_match,
            s.prompt_confidence,
            s.was_randomized,
            s.created_at as response_created
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

