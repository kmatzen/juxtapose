# Debugging: Identity & Mask Images Not Showing

## Quick Fix (Most Common Issues)

### 1. Restart the Server
The `image_pairs.txt` file is loaded at startup. After updating it, you MUST restart:

```bash
# Stop the server (Ctrl+C if running)
# Then restart:
cd /Users/matzen/git/survey
export DEV_MODE=true
./start.sh
```

### 2. Clear Browser Session
Your session might have cached the old pair list. Either:

**Option A: Use Incognito/Private Window**
- Open a new incognito/private browser window
- Navigate to your survey URL

**Option B: Clear Session**
- Visit: `http://localhost:5000/reset_session` (or your server URL)
- Click "Yes, Reset My Session"
- Start the survey again

### 3. Check Browser Console
Open browser DevTools (F12 or Right-click → Inspect) and check:

**Console Tab:**
- Look for JavaScript errors
- Look for "✓ Loaded X image pairs" message
- Check if `identity_urls` and `mask_url` are present in API responses

**Network Tab:**
- Check `/api/get_image_pair/0` response
- Verify the JSON includes `identity_urls` and `mask_url` fields

## Detailed Debugging Steps

### Step 1: Verify File is Being Loaded

Check server startup logs for:
```
✓ Loaded 15 image pairs from image_pairs.txt
```

If you see a different number or an error, there's a parsing issue.

### Step 2: Check API Response

Open browser console and run:
```javascript
fetch('/api/get_image_pair/0')
  .then(r => r.json())
  .then(data => console.log('Pair data:', data));
```

**Expected output for new format pairs:**
```json
{
  "id": 8,
  "prompt": "A person skiing down a snowy mountain",
  "method_a": "Method-A",
  "method_b": "Method-B",
  "image_a_url": "https://...",
  "image_b_url": "https://...",
  "identity_urls": "https://...",  // ← Should be present
  "mask_url": "https://...",        // ← Should be present
  "was_randomized": true,
  "total_pairs": 3
}
```

If `identity_urls` and `mask_url` are `null` or missing, the file isn't being parsed correctly.

### Step 3: Verify Database Schema

If you have an existing `survey.db`, you need to add the new columns:

```bash
cd /Users/matzen/git/survey

# Check if columns exist
sqlite3 survey.db "PRAGMA table_info(survey_responses);" | grep -E "identity|mask"

# If nothing shows up, run the migration:
sqlite3 survey.db <<EOF
ALTER TABLE survey_responses ADD COLUMN identity_urls TEXT;
ALTER TABLE survey_responses ADD COLUMN mask_url TEXT;
ALTER TABLE survey_responses ADD COLUMN better_mask_match TEXT;
ALTER TABLE survey_responses ADD COLUMN mask_confidence INTEGER;
ALTER TABLE survey_responses ADD COLUMN better_identity_match TEXT;
ALTER TABLE survey_responses ADD COLUMN identity_confidence INTEGER;
EOF

echo "Migration complete. Restart the server."
```

### Step 4: Check Which Pairs Are Being Sampled

In dev mode, only 3 random pairs are shown. You might be getting old format pairs by chance.

To force new format pairs, temporarily edit `image_pairs.txt` to ONLY include lines 8-10:

```
A person skiing down a snowy mountain	Method-A	Method-B	https://picsum.photos/seed/skiing8a/600/400	https://picsum.photos/seed/skiing8b/600/400	https://picsum.photos/seed/identity3/200/200	https://placehold.co/300x300/f3e5f5/8e24aa?text=Ski+Pose
A person surfing a large wave	Method-A	Method-B	https://picsum.photos/seed/surfing9a/600/400	https://picsum.photos/seed/surfing9b/600/400	https://picsum.photos/seed/identity4/200/200	https://placehold.co/300x300/e8f5e9/43a047?text=Wave+Position
A portrait in a garden setting	Method-A	Method-B	https://picsum.photos/seed/garden10a/600/400	https://picsum.photos/seed/garden10b/600/400	https://picsum.photos/seed/identity5/200/200,https://picsum.photos/seed/identity6/200/200	https://placehold.co/300x300/fce4ec/c2185b?text=Garden+Composition
```

Restart server, reset session, and you WILL see conditioning.

### Step 5: Verify JavaScript is Running

In browser console, check if the display function exists:
```javascript
console.log(typeof displayConditioningInputs);
// Should output: "function"
```

## Common Issues & Solutions

### Issue: "Only seeing 2 evaluation sections"
**Cause:** You're getting old format (5-field) pairs by random sampling.
**Solution:** Reset session to get new random sample, or temporarily edit file to only new format pairs.

### Issue: "Images not loading"
**Cause:** CORS or network issues with placeholder services.
**Solution:** Check browser console Network tab. If images fail to load, the URLs might be blocked. Try different placeholder services or use local images.

### Issue: "Server won't start"
**Cause:** Syntax error in `image_pairs.txt` (missing tabs, wrong number of fields).
**Solution:** Check server logs for parsing errors. Ensure tabs (not spaces) separate fields.

### Issue: "Conditioning sections visible but empty"
**Cause:** JavaScript error or image loading failure.
**Solution:** Check browser console for errors. Verify image URLs are accessible.

## Test Commands

Run these to verify everything is working:

```bash
# 1. Check file format (should show field counts)
cd /Users/matzen/git/survey
awk -F'\t' 'NF > 0 && !/^#/ {print NF, $1}' image_pairs.txt

# Expected output:
# 5 A serene mountain landscape at sunset
# 5 A futuristic city with flying cars
# 7 A person skiing down a snowy mountain
# 7 A person surfing a large wave
# etc.

# 2. Verify server loads correctly
export DEV_MODE=true
python -c "from src.survey.app import IMAGE_PAIRS; print(f'Loaded {len(IMAGE_PAIRS)} pairs'); print('Sample:', IMAGE_PAIRS[7] if len(IMAGE_PAIRS) > 7 else 'N/A')"

# 3. Check database
sqlite3 survey.db "SELECT name FROM sqlite_master WHERE type='table';"
```

## What You Should See

When working correctly:

1. **Yellow Boxes** above generated images (when identity/mask present)
2. **Identity Images** in a grid (150x150px thumbnails)
3. **Mask Image** centered below identity section
4. **4 Evaluation Sections** (not just 2):
   - Image Quality
   - Prompt Adherence
   - Mask Adherence ← NEW
   - Identity Preservation ← NEW

## Still Not Working?

If after all these steps it still doesn't work:

1. Share the output of:
   ```bash
   # Server startup log
   cat server.log  # or wherever your logs are
   
   # Image pairs count
   python -c "from src.survey.app import IMAGE_PAIRS; print(len(IMAGE_PAIRS))"
   
   # Sample pair
   python -c "from src.survey.app import IMAGE_PAIRS; import json; print(json.dumps(IMAGE_PAIRS[7], indent=2))"
   ```

2. Share browser console output (F12 → Console tab)

3. Share Network tab response for `/api/get_image_pair/0`

