# Database Migration Note

## Method Tracking Update

If you have an existing survey database (`survey.db`), you'll need to add the new `method_a` and `method_b` columns to your `survey_responses` table.

### Option 1: Manual Migration (Recommended for Production)

```sql
-- Add the new columns
ALTER TABLE survey_responses ADD COLUMN method_a TEXT;
ALTER TABLE survey_responses ADD COLUMN method_b TEXT;
```

You can run this SQL using any SQLite client or with Python:

```python
import sqlite3

db = sqlite3.connect('survey.db')
db.execute('ALTER TABLE survey_responses ADD COLUMN method_a TEXT')
db.execute('ALTER TABLE survey_responses ADD COLUMN method_b TEXT')
db.commit()
db.close()
```

### Option 2: Fresh Start (Dev/Testing Only)

If you're in development mode and don't need to keep existing data:

```bash
rm survey.db
# Then restart your app - it will create a new database with the correct schema
```

## What Changed

**Before:** The survey only stored "A" or "B" (UI positions) and a `was_randomized` flag.

**Now:** The survey stores:
- Which method was in position A (`method_a`)
- Which method was in position B (`method_b`)
- User's UI choice (still "A" or "B")
- Which actual method they preferred (computed in SQL queries)

## Benefits

- You can now see which generation methods users actually preferred
- The admin view shows both UI choices and actual method preferences
- Stats show method preference counts, not just positional bias
- CSV export includes method names for easier analysis

## Update Your IMAGE_PAIRS

Make sure each entry in `IMAGE_PAIRS` includes `method_a` and `method_b`:

```python
IMAGE_PAIRS = [
    {
        "id": 1,
        "prompt": "A serene mountain landscape at sunset",
        "method_a": "GPT-4-Vision",      # Your actual method name
        "method_b": "DALL-E-3",          # Your actual method name
        "image_a_url": "https://...",
        "image_b_url": "https://..."
    },
    # ... more pairs
]
```

