# Database Migration for Extended Survey Features

## New Columns Added to `survey_responses` Table

If you have an existing `survey.db`, you'll need to add these new columns:

```sql
-- Connect to your survey.db
sqlite3 survey.db

-- Add identity and mask URL storage
ALTER TABLE survey_responses ADD COLUMN identity_urls TEXT;
ALTER TABLE survey_responses ADD COLUMN mask_url TEXT;

-- Add mask adherence evaluation
ALTER TABLE survey_responses ADD COLUMN better_mask_match TEXT;
ALTER TABLE survey_responses ADD COLUMN mask_confidence INTEGER;

-- Add identity adherence evaluation
ALTER TABLE survey_responses ADD COLUMN better_identity_match TEXT;
ALTER TABLE survey_responses ADD COLUMN identity_confidence INTEGER;

-- Verify the schema
.schema survey_responses

.quit
```

## What Changed

### Before (2 evaluations):
1. Image Quality (better_image, image_confidence)
2. Prompt Adherence (better_prompt_match, prompt_confidence)

### After (4 evaluations):
1. Image Quality (better_image, image_confidence)
2. Prompt Adherence (better_prompt_match, prompt_confidence)
3. **Mask Adherence** (better_mask_match, mask_confidence) - NEW
4. **Identity Adherence** (better_identity_match, identity_confidence) - NEW

## Backward Compatibility

- Old format image pairs (5 fields) still work
- New mask/identity fields will be NULL for old-format pairs
- Survey UI only shows mask/identity questions when those images are present

