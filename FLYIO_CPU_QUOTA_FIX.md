# Fixing Fly.io CPU Quota Error

## The Problem

Error: "Your organization is limited to 4 CPU cores per machine"

This means you've hit the free tier limit. Common causes:
1. Other apps running on your Fly.io account
2. Multiple machines running for same app
3. Previous deployments not cleaned up

## Solution: Check What's Running

### Step 1: List All Your Apps
```bash
fly apps list
```

This shows all apps in your account.

### Step 2: Check Machines for Each App
```bash
fly status --app your-app-name
```

### Step 3: Scale Down or Remove Unused Apps

#### Option A: Scale Current App to Use Fewer Resources
```bash
# Use the absolute minimum for free tier
fly scale count 1 --app survey-app-silent-frost-2723
fly scale vm shared-cpu-1x --memory 256 --app survey-app-silent-frost-2723
```

#### Option B: Destroy Old/Unused Apps
```bash
fly apps destroy old-app-name
```

#### Option C: Stop Machines in Other Apps
```bash
fly machine list --app other-app-name
fly machine stop MACHINE_ID
```

## Quick Fix: Destroy This App and Recreate

If the app is new and hasn't deployed yet:

```bash
# Destroy the problematic app
fly apps destroy survey-app-silent-frost-2723

# Start fresh
fly launch --no-deploy

# Create volume
fly volumes create survey_data --size 1  # Use 1GB instead of 3GB

# Deploy
fly deploy
```

## Alternative: Use Render.com for Now

Since you already have Render set up, you could:
1. Stay on Render for testing
2. Add persistent disk when ready ($7/month)
3. Or export data regularly via admin panel (free)

Fly.io is great but has stricter free tier limits than Render for CPU.

## Check Your Fly.io Dashboard

Visit: https://fly.io/dashboard

Look at:
- "Machines" tab - see what's running
- "Billing" tab - see resource usage
- Multiple apps might be competing for the 4 CPU core limit
