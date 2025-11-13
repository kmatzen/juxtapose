# Updating Database on Render.com

## Option 1: Fresh Database (Recommended if No Important Data)

If you don't have important survey responses yet, just delete the old database:

1. **Go to Render Dashboard** → Your Service → Shell
2. **Run:**
   ```bash
   rm survey.db
   ```
3. **Restart the service** - it will create a new database with the correct schema automatically

## Option 2: Automatic Migration on Startup (Recommended for Production)

Add a migration script that runs automatically when the app starts.

### Create Migration Script

Create `src/survey/migrate_db.py`:

```python
import sqlite3
import os

def migrate_database():
    """Run database migrations"""
    db_path = 'survey.db'
    
    if not os.path.exists(db_path):
        print("No existing database, skipping migration")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if new columns already exist
    cursor.execute("PRAGMA table_info(survey_responses)")
    columns = [col[1] for col in cursor.fetchall()]
    
    migrations_needed = []
    
    if 'identity_urls' not in columns:
        migrations_needed.append(('identity_urls', 'TEXT'))
    if 'mask_url' not in columns:
        migrations_needed.append(('mask_url', 'TEXT'))
    if 'better_mask_match' not in columns:
        migrations_needed.append(('better_mask_match', 'TEXT'))
    if 'mask_confidence' not in columns:
        migrations_needed.append(('mask_confidence', 'INTEGER'))
    if 'better_identity_match' not in columns:
        migrations_needed.append(('better_identity_match', 'TEXT'))
    if 'identity_confidence' not in columns:
        migrations_needed.append(('identity_confidence', 'INTEGER'))
    
    if not migrations_needed:
        print("✓ Database schema is up to date")
        conn.close()
        return
    
    print(f"Running {len(migrations_needed)} migrations...")
    
    for col_name, col_type in migrations_needed:
        try:
            cursor.execute(f"ALTER TABLE survey_responses ADD COLUMN {col_name} {col_type}")
            print(f"  ✓ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower():
                print(f"  → Column {col_name} already exists, skipping")
            else:
                raise
    
    conn.commit()
    conn.close()
    print("✓ Database migration complete")

if __name__ == "__main__":
    migrate_database()
```

### Update app.py to run migration

Add at the top of `src/survey/app.py`, right before `init_db()`:

```python
# Run migrations before initializing
from src.survey.migrate_db import migrate_database
migrate_database()

# Initialize database on startup
init_db()
```

This will automatically update the database schema on every deployment!

## Option 3: Manual Migration via Render Shell

If you want to manually migrate an existing database:

1. **Go to Render Dashboard** → Your Service → **Shell** button
2. **Run the migration SQL:**
   ```bash
   sqlite3 survey.db <<EOF
   ALTER TABLE survey_responses ADD COLUMN identity_urls TEXT;
   ALTER TABLE survey_responses ADD COLUMN mask_url TEXT;
   ALTER TABLE survey_responses ADD COLUMN better_mask_match TEXT;
   ALTER TABLE survey_responses ADD COLUMN mask_confidence INTEGER;
   ALTER TABLE survey_responses ADD COLUMN better_identity_match TEXT;
   ALTER TABLE survey_responses ADD COLUMN identity_confidence INTEGER;
   .quit
   EOF
   ```
3. **Verify:**
   ```bash
   sqlite3 survey.db "PRAGMA table_info(survey_responses);" | grep -E "identity|mask"
   ```

You should see the 6 new columns.

## Option 4: Download, Migrate, Re-upload (Last Resort)

If Render Shell doesn't work:

1. **Download current database:**
   ```bash
   # From Render Shell
   cat survey.db | base64
   ```
   Copy the output, decode locally, and save as `survey.db`

2. **Run migration locally:**
   ```bash
   sqlite3 survey.db < DATABASE_MIGRATION_EXTENDED.sql
   ```

3. **Re-upload:**
   - Stop the Render service
   - Use Render's file upload or replace via git commit
   - Restart service

## Verification

After migration, check the schema:

```bash
# Via Render Shell
sqlite3 survey.db "PRAGMA table_info(survey_responses);"
```

You should see output including:
```
15|identity_urls|TEXT|0||0
16|mask_url|TEXT|0||0
17|better_mask_match|TEXT|0||0
18|mask_confidence|INTEGER|0||0
19|better_identity_match|TEXT|0||0
20|identity_confidence|INTEGER|0||0
```

## Best Practice for Future

Use **Option 2** (automatic migration script) so that future schema changes happen automatically on deployment without manual intervention.

## Important Notes

- **SQLite on Render**: Since Render uses ephemeral file systems for free plans, your `survey.db` might get deleted on restarts. For production, consider:
  - Using Render's Persistent Disk feature
  - Moving to PostgreSQL (Render's managed database)
  - Regular database backups via the admin export feature

- **Backup First**: If you have important data, always export via the admin panel (`/api/admin/export`) before making schema changes.

