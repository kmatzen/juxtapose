# ✅ Fly.io Deployment Successful!

## 🌐 Your Survey is Live

**URL:** https://survey-app-silent-frost-2723.fly.dev/

## 📊 Current Status

```
App:      survey-app-silent-frost-2723
Region:   sjc (San Jose, California)
Status:   ✅ Running (started)
Health:   ✅ Passing
Database: /data/survey.db (persistent volume)
Pairs:    15 image pairs loaded
Dev Mode: false
```

## 🔧 What Was Fixed

1. **CPU Quota Issue** → Switched from Paketo buildpack to Dockerfile
2. **Health Check Failing** → Added dedicated `/health` endpoint
3. **Missing Utilities** → Added `curl` and `procps` for SSH debugging
4. **Auto-Stop Issue** → Resolved by adding credit card (moved from free tier)

## 💾 Persistent Storage

Your SQLite database is stored on a **3GB persistent volume** at `/data/survey.db`. This means:
- ✅ Data survives app restarts
- ✅ Data survives deployments
- ✅ Safe for production use

## 🛠️ Useful Commands

```bash
# View app status
fly status

# View logs
fly logs

# SSH into the machine
fly ssh console

# Restart the app
fly machine restart 7849775b377de8

# Deploy updates
fly deploy

# Scale resources (if needed)
fly scale memory 512  # Increase to 512MB
```

## 📈 Admin Access

Admin panel: https://survey-app-silent-frost-2723.fly.dev/admin/login
Password: `admin123` (change via `ADMIN_PASSWORD` environment variable)

## 🔐 Environment Variables

Set via Fly.io secrets:

```bash
# Set admin password
fly secrets set ADMIN_PASSWORD=your-secure-password

# Set dev mode (for testing)
fly secrets set DEV_MODE=true

# Set referral codes
fly secrets set REFERRAL_CODES=CODE1,CODE2,CODE3
```

## 💰 Cost Estimate

With the hobby plan (credit card on file):
- **Shared CPU (256MB)**: ~$0.0000008/second = ~$2/month
- **3GB Persistent Volume**: $0.15/GB/month = $0.45/month
- **Estimated Total**: ~$2.50/month

## 🚀 Next Steps

1. Test the survey at https://survey-app-silent-frost-2723.fly.dev/
2. Update admin password: `fly secrets set ADMIN_PASSWORD=your-password`
3. Add your real image pairs to `image_pairs.txt`
4. Deploy updates: `git push origin main && fly deploy`

## 📝 Key Features Now Live

- ✅ Identity & mask conditioning image display
- ✅ 4 evaluation questions per pair (image quality, prompt adherence, mask adherence, identity preservation)
- ✅ Referral code gating (current code: `ADOBE2025`)
- ✅ Random sampling of up to 30 pairs per user
- ✅ Session management & retake warnings
- ✅ Device info collection
- ✅ Admin dashboard with CSV export
- ✅ Persistent database storage

## 🐛 Debugging

If you encounter issues:

```bash
# Check health internally
fly ssh console -C "curl http://localhost:8000/health"

# Check gunicorn processes
fly ssh console -C "ps -ef | grep gunicorn"

# View database
fly ssh console -C "ls -lh /data"

# Check recent logs
fly logs
```

## 🔄 Comparison: Fly.io vs Render.com

Both are now working! Choose based on your needs:

**Fly.io (Current)**
- ✅ Free persistent storage (3GB volume)
- ✅ Faster cold starts
- ✅ Better SSH debugging tools
- 💰 ~$2.50/month with hobby plan
- ⚠️ Required credit card to prevent auto-stop

**Render.com (Alternative)**
- ✅ Simpler setup
- ✅ Auto-deploys from GitHub
- ⚠️ Free tier has no persistent disk (data lost on restart)
- 💰 $7/month for persistent disk

---

**Recommendation:** Stick with Fly.io now that it's working! You get persistent storage on the hobby plan.

