# Survey Web Application

A Flask-based survey application for collecting user evaluations of question pairs. Participants evaluate 30 question pairs, comparing which question is better and which adheres better to a given prompt.

## Features

- **User Tracking**: Email-based tracking to prevent duplicate submissions
- **Demographics Collection**: Customizable demographics for image generation studies
- **Image Comparison**: Dual evaluation (quality + prompt adherence) with confidence levels
- **30 Image Pairs**: Sequential evaluation with progress tracking
- **Randomization**: Image order (A/B) is randomized 50% of the time to prevent bias
- **Admin Interface**: Password-protected dashboard to view and export results
- **SQLite Database**: Simple file-based storage for all responses
- **Responsive Design**: Works on desktop and mobile devices
- **Device Tracking**: Browser, OS, screen resolution automatically collected
- **Dev Mode**: Auto-fill forms and use only 3 pairs for fast testing 🔧

## Quick Start (Dev Mode)

Want to test immediately? Run:

```bash
./start.sh
```

This enables **DEV MODE** which:
- 🔧 Auto-fills all form fields with test data
- 🚀 Uses only 3 image pairs instead of 30
- ⚡ Makes testing super fast!
- 🔴 Shows a red "DEV MODE" badge in the top-right

See `QUICKSTART.md` for more details.

## Setup Instructions

### 1. Install uv (Recommended - Fast!)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Why uv?** It's 10-100x faster than pip! See `UV_GUIDE.md` for details.

### 2. Install Dependencies

```bash
uv sync
```

Or if you prefer pip:
```bash
pip install -r requirements.txt  # (will generate if needed)
```

### 3. Configure Your Image Pairs

**Easy!** Just edit `image_pairs.txt` - a simple tab-separated file:

```
# Format: prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url
A serene mountain landscape at sunset	GPT-4-Vision	DALL-E-3	https://example.com/img1a.jpg	https://example.com/img1b.jpg
A futuristic city with flying cars	GPT-4-Vision	DALL-E-3	https://example.com/img2a.jpg	https://example.com/img2b.jpg
```

**Benefits:**
- No Python code editing needed!
- Easy to create in Excel/Google Sheets (export as TSV)
- Comments supported (lines starting with #)
- Auto-creates sample file if missing

See `IMAGE_PAIRS_FORMAT.md` for complete documentation and examples.

**Method Tracking:** The `method_a` and `method_b` fields identify which generation method created each image. When images are randomized (50% of the time), the method names are swapped along with the images, allowing you to see which actual method users preferred.

### 4. Set Environment Variables (Optional but Recommended)

```bash
# For production, set a secure secret key
export SECRET_KEY="your-secret-key-here"

# Set admin password (default is 'admin123')
export ADMIN_PASSWORD="your-secure-password"

# Enable dev mode for testing (auto-fill forms, only 3 pairs)
export DEV_MODE=true

# Optional: Set custom port
export PORT=5000
```

### 5. Run the Application

```bash
# With uv (recommended)
uv run python run.py

# Or use the convenience script (auto-enables DEV MODE)
./start.sh

# Or directly with python (if you have dependencies installed)
python run.py
```

The app will run on `http://localhost:5000` (or your custom PORT).

## Deployment Options

### Option 1: Render.com (Recommended - Easiest)

**Free tier available!** Most Heroku-like experience.

1. Push code to GitHub
2. Sign up at [render.com](https://render.com)
3. Create new Web Service from your GitHub repo
4. Set `ADMIN_PASSWORD` environment variable
5. Deploy!

**Pros:** Easy, auto-deploy from Git, free tier  
**Cons:** Sleeps after 15 min inactivity (30s wake-up), ephemeral storage on free tier

See `DEPLOYMENT.md` for detailed instructions.

### Option 2: Fly.io (Best for Always-On)

**Free tier: 3 VMs, persistent storage!** Best for production SQLite.

1. Install flyctl: `brew install flyctl`
2. Run: `fly launch --name your-survey-app`
3. Create volume: `fly volumes create survey_data --size 1`
4. Set secrets: `fly secrets set ADMIN_PASSWORD="yourpass"`
5. Deploy: `fly deploy`

**Pros:** Always on, persistent SQLite, truly free  
**Cons:** Requires CLI installation

See `DEPLOYMENT.md` for detailed instructions.

### Option 3: Railway.app

**$5 free credit per month** - Simple deployment.

1. Sign up at [railway.app](https://railway.app)
2. Deploy from GitHub repo
3. Set environment variables
4. Deploy!

**Pros:** Very easy, good for testing  
**Cons:** Credit-based (runs out with heavy traffic)

### Option 4: Local + ngrok (Testing Only)

**What is ngrok?** Creates a tunnel to your local machine.

1. Download ngrok: https://ngrok.com/download
2. Run Flask: `python app.py`
3. Run ngrok: `ngrok http 5000`
4. Share the public URL

**Pros:** Free, instant, no server setup  
**Cons:** Computer must stay on, URL changes each restart

### Option 5: AWS EC2 / Google Cloud (If You Have Access)

For full control, deploy to cloud VMs. See standard Flask deployment guides.

**Note:** Heroku eliminated their free tier in 2022 - use Render or Fly.io instead!

## Using the Application

### For Participants

1. Visit the survey URL
2. Fill in demographics (occupation, image gen experience, AI familiarity, etc.)
3. Evaluate 30 image pairs:
   - **Image Quality**: Select which image looks better (A or B) + confidence (1-5 Likert scale)
   - **Prompt Adherence**: Select which image better matches the prompt (A or B) + confidence (1-5)
   - Click images for a larger view (lightbox)
4. Submit responses - participants can only complete once per email
5. Retake warning shown if email was previously used

### For Administrators

1. Visit `/admin/login`
2. Enter admin password (default: `admin123`)
3. View dashboard with:
   - Total participants count
   - **Method preferences** by actual generation method (not just A/B position)
   - Average confidence scores (image quality / prompt adherence)
   - Toggle between Demographics View and Responses View
   - Detailed response table with method resolution
4. Export all results as CSV for analysis

## Database

The app uses SQLite with three tables:

- **participants**: Session tracking + device information (browser, OS, screen, etc.)
- **demographics**: User information (email, occupation, AI experience, etc.)
- **survey_responses**: Image pair evaluations (30 rows per participant)
  - Stores both UI choice (A/B) and actual method names
  - Includes `method_a`, `method_b` columns for method tracking
  - Admin queries compute which method was actually preferred

Database file: `survey.db` (created automatically on first run)

**Backup:** Simply copy the `survey.db` file.

**Migration:** If updating from an older version without method tracking, see `MIGRATION_NOTE.md` for SQL migration scripts.

## File Structure

```
survey/
├── pyproject.toml         # Project configuration
├── requirements.txt       # Python dependencies (generated)
├── run.py                 # Application entry point
├── survey.db             # SQLite database (created on first run)
└── src/
    └── survey/           # Main package
        ├── __init__.py
        ├── app.py        # Flask backend
        ├── templates/
        │   ├── index.html       # Main survey page
        │   ├── thank_you.html   # Completion page
        │   ├── admin.html       # Admin dashboard
        │   └── admin_login.html # Admin login
        └── static/
            ├── style.css  # All styles
            └── script.js  # Frontend logic
```

## Security Considerations

1. **Change the admin password** in production:
   ```bash
   export ADMIN_PASSWORD="your-secure-password"
   ```

2. **Set a secure secret key**:
   ```bash
   export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   ```

3. **Use HTTPS**: ngrok provides this automatically. For custom domains, use Let's Encrypt.

4. **Email Privacy**: Emails are stored in the database. Consider:
   - Adding a privacy policy
   - Hashing emails if you only need uniqueness
   - GDPR compliance if collecting EU data

5. **Rate Limiting**: For production, add rate limiting to prevent abuse.

## Troubleshooting

### Port already in use
```bash
# Find process using port 5000
lsof -i :5000
# Kill it
kill -9 <PID>
```

### Database locked
- Only one process can write to SQLite at once
- For high traffic, migrate to PostgreSQL

### ngrok connection issues
- Free tier has connection limits
- Upgrade to paid plan or deploy to cloud

## Customization

### Changing Colors
Edit `static/style.css` - main brand color is `#4A90E2`

### Adding Questions
Edit the `QUESTION_PAIRS` list in `app.py`

### Adding Demographics Fields
1. Add fields to `templates/index.html`
2. Update database schema in `app.py` `init_db()`
3. Update the demographics submission handler

## Support

For issues or questions, check:
- Flask documentation: https://flask.palletsprojects.com/
- ngrok documentation: https://ngrok.com/docs

## License

This is a custom survey application. Use and modify as needed.

