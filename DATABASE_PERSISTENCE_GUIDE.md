# Database Persistence on Render.com

## The Problem

SQLite databases on Render's **free tier** use ephemeral storage:
- ✅ Survives normal restarts/redeploys
- ❌ Lost when service sleeps (15 min inactivity)
- ❌ Lost when Render moves infrastructure
- ❌ Not reliable for production data

## Solutions (Ranked by Reliability)

### 🥇 Option 1: PostgreSQL (Best for Production)

Switch from SQLite to PostgreSQL using Render's managed database.

**Pros:**
- Fully persistent, never loses data
- Better for concurrent users
- Professional solution
- Free tier available for Postgres too!

**Cons:**
- Requires code changes (SQLAlchemy or raw SQL adaptation)
- More complex setup

**Setup:**
1. Create a PostgreSQL database on Render
2. Update app to use PostgreSQL instead of SQLite
3. Use connection string from Render

### 🥈 Option 2: Persistent Disk (Good for Small Projects)

Add a persistent disk to your web service (requires paid plan ~$7/mo).

**Pros:**
- Keep using SQLite
- Minimal code changes
- Simple to set up

**Cons:**
- Costs money ($7/mo for starter plan + disk)
- Still single-server limitation

**Setup:**
Already configured in `render.yaml` (commented out):
```yaml
disk:
  name: survey-data
  mountPath: /opt/render/project/src
  sizeGB: 1
```

To enable: Uncomment in Render dashboard or apply the updated `render.yaml`.

### 🥉 Option 3: External Database Service (SQLite Compatible)

Use a service like Turso (SQLite-as-a-service) or LiteFS.

**Pros:**
- Keep using SQLite
- Fully persistent
- Some have free tiers

**Cons:**
- External dependency
- Need to update connection code

### 🆓 Option 4: Regular Backups (Free Tier Workaround)

Keep using ephemeral storage but backup frequently.

**Automatic Backup Script:**

Create `backup_db.py`:
```python
#!/usr/bin/env python3
"""
Automated database backup script.
Run via cron or scheduled task.
"""
import os
import requests
import schedule
import time
from datetime import datetime

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
BASE_URL = os.getenv('SURVEY_URL', 'https://your-app.onrender.com')
BACKUP_DIR = os.getenv('BACKUP_DIR', './backups')

def backup_database():
    """Download CSV backup from admin endpoint"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{BACKUP_DIR}/survey_backup_{timestamp}.csv"
    
    # Login first
    session = requests.Session()
    session.post(f"{BASE_URL}/admin/login", data={'password': ADMIN_PASSWORD})
    
    # Download export
    response = session.get(f"{BASE_URL}/api/admin/export")
    
    if response.status_code == 200:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        with open(backup_file, 'wb') as f:
            f.write(response.content)
        print(f"✓ Backup saved: {backup_file}")
        return True
    else:
        print(f"✗ Backup failed: {response.status_code}")
        return False

# Schedule daily backups
schedule.every().day.at("02:00").do(backup_database)

# Or backup every 6 hours
schedule.every(6).hours.do(backup_database)

if __name__ == "__main__":
    print("Starting automated backup service...")
    backup_database()  # Run immediately
    while True:
        schedule.run_pending()
        time.sleep(60)
```

**Manual Backup (Via Admin Panel):**
- Visit `/admin` regularly
- Click "Export to CSV"
- Save the file locally

**Pros:**
- Free!
- Works with current setup
- No code changes needed

**Cons:**
- Manual effort (unless automated)
- Data loss possible between backups
- Not real-time

## 📊 Comparison Table

| Solution | Cost | Persistence | Effort | Best For |
|----------|------|-------------|--------|----------|
| PostgreSQL | Free/Paid | 100% | Medium | Production |
| Persistent Disk | $7/mo | 100% | Low | Small projects |
| External DB | Free/Paid | 100% | Medium | Specific needs |
| Regular Backups | Free | Partial | Low/Medium | Testing/Dev |
| Do Nothing | Free | ~80% | None | Quick tests only |

## 🎯 My Recommendation

**For your case (image generation survey):**

**If gathering real research data:** Use **PostgreSQL** (Option 1)
- Free tier available
- Never lose data
- More professional

**If just testing/prototyping:** Use **Regular Backups** (Option 4)
- Keep current setup
- Export CSV daily via admin panel
- Upgrade later when needed

**If you want to pay:** Use **Persistent Disk** (Option 2)
- Simplest upgrade
- $7/month
- Enable in Render dashboard

## 🚀 Quick Start: Enable Persistent Disk Now

If you want to enable persistent disk right now:

1. **Go to Render Dashboard** → Your Service → Settings
2. Scroll to **Disks** section
3. Click **Add Disk**:
   - Name: `survey-data`
   - Mount Path: `/opt/render/project/src`
   - Size: 1 GB
4. **Save Changes** → Service will restart with persistent storage
5. Database now persists forever! ✨

**Cost:** Requires Starter plan ($7/month for the service, disk included in most plans)

## 📝 Current Status

Right now, your survey is using **ephemeral storage**. This means:

✅ Good for: Testing, development, prototyping
❌ Bad for: Production research data, long-term studies

**Action needed before collecting real research data!**

Choose one of the options above based on your needs and timeline.

