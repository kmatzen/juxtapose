# Deployment Guide

Since you can't use EC2 and Heroku is no longer free, here are your best options with step-by-step instructions.

## Option 1: Render (Recommended - Easiest)

**Pros:** Free tier, most like Heroku, automatic deploys from Git  
**Cons:** Sleeps after 15 min inactivity (30s wake-up time)

### Preparation:

Generate `requirements.txt` from `pyproject.toml` (for compatibility):
```bash
uv pip compile pyproject.toml -o requirements.txt
git add requirements.txt pyproject.toml
git commit -m "Add uv support"
```

### Steps:

1. **Push your code to GitHub** (if not already)
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/survey.git
   git push -u origin main
   ```

2. **Sign up at [render.com](https://render.com)** (free)

3. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Render will auto-detect the `render.yaml` config

4. **Set Environment Variables**
   - Go to "Environment" tab
   - Add: `ADMIN_PASSWORD` = your secure password
   - `SECRET_KEY` is auto-generated

5. **Deploy!**
   - Click "Create Web Service"
   - Wait 2-3 minutes
   - Your app will be live at: `https://survey-app-xxxx.onrender.com`

### Important: SQLite on Render

⚠️ Render's free tier has **ephemeral storage** - your database resets when the server sleeps or restarts!

**Solutions:**
- **Use their free PostgreSQL** (recommended for production)
- **Accept data loss** (OK for testing)
- **Backup regularly** via the admin export feature
- **Upgrade to paid tier** ($7/month) for persistent disk

To use PostgreSQL instead of SQLite, see the migration section below.

---

## Option 2: Fly.io (Best for Always-On + SQLite)

**Pros:** Truly free tier, always on, persistent storage, great for SQLite  
**Cons:** Slightly more CLI setup

### Steps:

1. **Install Fly CLI**
   ```bash
   # Mac
   brew install flyctl
   
   # Linux/WSL
   curl -L https://fly.io/install.sh | sh
   
   # Windows
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Sign up and authenticate**
   ```bash
   fly auth signup  # or: fly auth login
   ```

3. **Launch your app** (from the survey directory)
   ```bash
   fly launch --name your-survey-app
   ```
   - It will detect the `fly.toml` config
   - Say "Yes" to copying configuration
   - Say "No" to PostgreSQL (we're using SQLite)
   - Say "No" to Redis

4. **Create persistent volume for database**
   ```bash
   fly volumes create survey_data --size 1 --region sjc
   ```

5. **Set secrets**
   ```bash
   fly secrets set ADMIN_PASSWORD="your-secure-password"
   fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
   ```

6. **Deploy**
   ```bash
   fly deploy
   ```

7. **Open your app**
   ```bash
   fly open
   ```

Your app will be live at: `https://your-survey-app.fly.dev`

### Persistent Storage on Fly.io

To mount the volume, add this to `app.py` (I'll do this for you):

```python
# Use /data/survey.db if volume is mounted, otherwise survey.db
DATABASE = '/data/survey.db' if os.path.exists('/data') else 'survey.db'
```

---

## Option 3: Railway

**Pros:** Simple, $5 free credit/month  
**Cons:** Credits run out with heavy traffic

### Steps:

1. **Go to [railway.app](https://railway.app)** and sign up

2. **New Project** → **Deploy from GitHub**
   - Connect your repo
   - Railway auto-detects Python

3. **Add Environment Variables**
   - Go to Variables tab
   - Add `ADMIN_PASSWORD` and `SECRET_KEY`

4. **Deploy**
   - Automatic
   - Get your URL from the Deployments tab

⚠️ Railway is metered - $5 credit is ~500 hours or ~200k requests

---

## Option 4: PythonAnywhere (Free but Limited)

**Pros:** Actually free forever, always on  
**Cons:** Limited performance, manual setup

### Steps:

1. **Sign up at [pythonanywhere.com](https://www.pythonanywhere.com)** (free account)

2. **Upload your code**
   - Use their web-based file browser
   - Or clone from Git in their bash console

3. **Create virtual environment**
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 survey
   pip install -r requirements.txt
   ```

4. **Configure Web App**
   - Web tab → Add new web app
   - Manual configuration → Python 3.10
   - Set source code path: `/home/yourusername/survey`
   - Set WSGI file to point to your app

5. **Set environment variables**
   - In WSGI configuration file

Your app will be at: `https://yourusername.pythonanywhere.com`

---

## Migrating from SQLite to PostgreSQL (If Needed)

If you use Render or another platform with free PostgreSQL, update your app:

1. **Install psycopg2**
   ```bash
   pip install psycopg2-binary
   ```

2. **Update requirements.txt**
   ```
   Flask==3.0.0
   gunicorn==21.2.0
   psycopg2-binary==2.9.9
   ```

3. **Update app.py** (I can help with this if needed)

---

## Comparison Table

| Platform | Free Tier | Always On | SQLite OK | Setup Difficulty | Best For |
|----------|-----------|-----------|-----------|------------------|----------|
| **Render** | ✅ 750hrs | ❌ Sleeps | ⚠️ Ephemeral | ⭐ Easy | Testing, low traffic |
| **Fly.io** | ✅ 3 VMs | ✅ Yes | ✅ With volume | ⭐⭐ Medium | Production, SQLite |
| **Railway** | ✅ $5/mo | ✅ Yes | ✅ Yes | ⭐ Easy | Short-term projects |
| **PythonAnywhere** | ✅ Forever | ✅ Yes | ✅ Yes | ⭐⭐⭐ Hard | Long-term, low traffic |

---

## My Recommendation

**For your survey app:**

1. **Start with Render** - Easiest to deploy, test if the sleep time is acceptable
2. **If you need always-on** - Switch to Fly.io (free + persistent SQLite)
3. **For serious production** - Fly.io paid ($2-5/month) or Render paid ($7/month)

---

## Quick Deploy Commands

### Render:
```bash
git push  # Auto-deploys if connected to GitHub
```

### Fly.io:
```bash
fly deploy
```

### Railway:
```bash
git push  # Auto-deploys
```

---

## Need Help?

Each platform has great docs:
- Render: https://render.com/docs
- Fly.io: https://fly.io/docs
- Railway: https://docs.railway.app
- PythonAnywhere: https://help.pythonanywhere.com

Let me know which platform you choose and I can help with any issues!

