# Referral Code Feature

The survey includes an optional **access code gate** to control who can participate. This feature is useful for:
- Limiting survey access to specific groups
- Tracking different distribution channels
- Preventing unauthorized participation
- Analyzing results by referral source

## Visual Experience

When enabled, users see a beautiful lock screen 🔒 before accessing the survey, requiring them to enter a valid access code.

## Configuration

There are three ways to configure referral codes:

### Option 1: Environment Variable (Recommended for Production)

Set a comma-separated list of valid codes:

```bash
export REFERRAL_CODES="CODE1,CODE2,CODE3"
```

Example:
```bash
export REFERRAL_CODES="ADOBE2025,RESEARCH2025,PILOT"
```

### Option 2: Edit app.py (Good for Development)

Edit `/Users/matzen/git/survey/src/survey/app.py` around line 22:

```python
if not REFERRAL_CODES:
    REFERRAL_CODES = {
        'ADOBE2025',
        'RESEARCH',
        'PILOT',
    }
```

### Option 3: Disable (No Gate)

To disable the referral code requirement:

```bash
export REFERRAL_CODES=""  # Empty = no requirement
```

Or in `app.py`:
```python
if not REFERRAL_CODES:
    REFERRAL_CODES = {}  # Empty set = disabled
```

## How It Works

1. **User visits survey** → Sees access code screen
2. **Enters code** → Validates against your list
3. **Valid code** → Proceeds to demographics
4. **Invalid code** → Error message, can retry
5. **Session storage** → Code stored in session, no re-entry needed
6. **Database tracking** → Code saved with participant data

### Code Validation

- **Case-insensitive**: "adobe2025", "ADOBE2025", "Adobe2025" all work
- **Trimmed**: Spaces are removed automatically
- **No expiration**: Codes remain valid until you remove them

## Dev Mode Behavior

When `DEV_MODE=true`:
- ✅ Referral code requirement is **automatically bypassed**
- ✅ Users go straight to demographics
- ✅ Makes testing much faster
- ✅ No need to remember test codes

This is the default behavior when running `./start.sh`

## Database Tracking

The `participants` table includes a `referral_code` column that stores which code each participant used. This allows you to:

### In Admin Interface

The CSV export includes the `referral_code` column, allowing you to:
- Count participants per code
- Compare demographics across codes
- Analyze response quality by source
- Track conversion rates

### Example Analysis

```python
import pandas as pd

df = pd.read_csv('survey_results.csv')

# Count by referral code
print(df['referral_code'].value_counts())

# Demographics by code
print(df.groupby('referral_code')['occupation'].value_counts())

# Response rates
print(df.groupby('referral_code').size())
```

## Use Cases

### 1. Multiple Distribution Channels

```python
REFERRAL_CODES = {
    'EMAIL-2025',      # Email campaign
    'SOCIAL-MEDIA',    # Twitter/LinkedIn
    'CONFERENCE',      # Conference attendees
    'INTERNAL',        # Company employees
    'BETA-TESTERS',    # Beta test group
}
```

### 2. Time-Limited Batches

```python
REFERRAL_CODES = {
    'BATCH-JAN',
    'BATCH-FEB',
    'BATCH-MAR',
}
```

Remove old codes and add new ones monthly.

### 3. Team-Based Distribution

```python
REFERRAL_CODES = {
    'TEAM-RESEARCH',
    'TEAM-MARKETING',
    'TEAM-DESIGN',
    'TEAM-PRODUCT',
}
```

Track which team members brought the best participants.

### 4. Incentive Tracking

```python
REFERRAL_CODES = {
    'GIFT-CARD-A',     # $10 Amazon gift card
    'GIFT-CARD-B',     # $25 Amazon gift card
    'PREMIUM-ACCESS',  # Early access to results
}
```

Different codes for different incentive levels.

## Security Considerations

### What the Referral Code Is NOT

- ❌ Not a password or authentication system
- ❌ Not encryption or data protection
- ❌ Not PII (personally identifiable information)
- ❌ Not a guarantee of data privacy

### What It IS

- ✅ An access control mechanism
- ✅ A tracking and analytics tool
- ✅ A participation gating system
- ✅ A distribution channel identifier

### Best Practices

1. **Use descriptive codes** that don't reveal sensitive information
   - ✅ Good: `RESEARCH2025`, `PILOT-GROUP`, `BETA`
   - ❌ Avoid: `CONFIDENTIAL`, `SECRET-PROJECT`, `INTERNAL-ONLY`

2. **Don't use codes as security**
   - Referral codes can be shared and will be visible in URLs
   - They are stored in plain text in the database
   - Anyone with a code can participate

3. **Rotate codes periodically**
   - Remove old codes after campaigns end
   - Add new codes for new campaigns
   - Monitor usage to detect sharing

4. **Combine with other controls**
   - Use admin password protection
   - Monitor for duplicate emails
   - Check response quality manually

## Session Reset Behavior

When a user clicks "Start Over" or resets their session:
- Their session is cleared completely
- They are redirected back to the referral code page
- They must re-enter a valid code
- This prevents abuse on shared computers

## Deployment

### Render.com

Add to your environment variables in the Render dashboard:

```
REFERRAL_CODES = CODE1,CODE2,CODE3
```

### Fly.io

```bash
fly secrets set REFERRAL_CODES="CODE1,CODE2,CODE3"
```

### Railway

Add in the Variables tab:
```
REFERRAL_CODES = CODE1,CODE2,CODE3
```

### Docker

```bash
docker run -e REFERRAL_CODES="CODE1,CODE2,CODE3" your-image
```

## Troubleshooting

### "Invalid referral code" but code is correct

1. Check case sensitivity - codes are converted to UPPERCASE
2. Check for spaces - they're trimmed automatically
3. Verify code is in the set/environment variable
4. Restart the app after changing codes in app.py

### Codes not updating after changing app.py

The app needs to be restarted to pick up changes to the `REFERRAL_CODES` set in Python code.

Environment variables are read at startup, not on every request.

### Dev mode still asking for code

Check that `DEV_MODE=true` is actually set:

```bash
echo $DEV_MODE  # Should print: true
```

### Want to see which code a user entered

Check the CSV export from the admin interface - it includes a `referral_code` column.

## Migration for Existing Databases

If you have an existing `survey.db` from before the referral code feature was added, you need to add the `referral_code` column:

```sql
sqlite3 survey.db
ALTER TABLE participants ADD COLUMN referral_code TEXT;
.quit
```

See `MIGRATION_NOTE.md` for complete migration instructions.

## Summary

✅ **Optional feature** - disable by setting empty codes  
✅ **Dev mode bypass** - never slows down testing  
✅ **Database tracked** - analyze by referral source  
✅ **Case-insensitive** - user-friendly  
✅ **Session-based** - no re-entry needed  
✅ **Beautiful UI** - professional lock screen  

The referral code feature gives you fine-grained control over survey access while maintaining a smooth user experience.

