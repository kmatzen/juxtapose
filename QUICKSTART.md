# Quick Start Guide

## Get Running in 3 Steps

### Step 1: Add Your Questions

Edit `app.py` around line 17 and replace the `QUESTION_PAIRS` list with your 30 actual question pairs. See `sample_questions.py` for the format.

### Step 2: Install uv (Fast Python Package Manager)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with homebrew
brew install uv
```

### Step 3: Start the Server

```bash
./start.sh
```

Or manually:
```bash
uv sync           # Install dependencies (super fast!)
uv run python app.py
```

### Step 4: Make it Public with ngrok

1. Download ngrok: https://ngrok.com/download
2. Run: `ngrok http 5000`
3. Share the URL it gives you (e.g., `https://abc123.ngrok.io`)

## Access Points

- **Survey**: `http://localhost:5000` (or your ngrok URL)
- **Admin**: `http://localhost:5000/admin/login`
  - Default password: `admin123` (change via `export ADMIN_PASSWORD="newpass"`)

## What Participants Will Do

1. Enter email and demographics
2. Evaluate 30 question pairs:
   - Pick which is better (A, B, or Equal)
   - Rate confidence (1-5)
   - Pick which adheres better to the prompt
3. Can only submit once per email

## Viewing Results

1. Go to `/admin/login`
2. Enter admin password
3. View stats and detailed results
4. Export to CSV

## Data Storage

All data is saved in `survey.db` (SQLite file). To backup, just copy this file.

## Important Security Notes

⚠️ **Before sharing publicly:**

1. Change admin password:
   ```bash
   export ADMIN_PASSWORD="your-secure-password"
   ```

2. Set secure secret key:
   ```bash
   export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   ```

3. Consider privacy implications of storing emails

## Troubleshooting

**Port 5000 already in use?**
```bash
export PORT=8080  # Use different port
python app.py
```

**Need to reset everything?**
```bash
rm survey.db  # Deletes all data - be careful
python app.py  # Creates fresh database
```

**ngrok URL changes every time?**
- Free tier assigns random URLs
- Upgrade to paid plan for persistent URLs
- Or deploy to a real server (see README.md)

## Next Steps

- See `README.md` for detailed documentation
- See `sample_questions.py` for question format examples
- For production deployment options, see "Deployment Options" in README.md

