"""
Database migration script for survey application.
Automatically adds new columns to existing databases.
"""
import sqlite3
import os

def migrate_database():
    """Run database migrations to add new columns if they don't exist"""
    db_path = 'survey.db'
    
    if not os.path.exists(db_path):
        print("→ No existing database found, skipping migration (will be created fresh)")
        return
    
    print("→ Checking database schema...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if survey_responses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='survey_responses'")
        if not cursor.fetchone():
            print("→ survey_responses table doesn't exist yet, skipping migration")
            conn.close()
            return
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(survey_responses)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}  # {name: type}
        
        # Define required columns for identity/mask feature
        required_columns = {
            'identity_urls': 'TEXT',
            'mask_url': 'TEXT',
            'better_mask_match': 'TEXT',
            'mask_confidence': 'INTEGER',
            'better_identity_match': 'TEXT',
            'identity_confidence': 'INTEGER'
        }
        
        # Find missing columns
        missing_columns = {
            name: col_type 
            for name, col_type in required_columns.items() 
            if name not in columns
        }
        
        if not missing_columns:
            print("✓ Database schema is up to date (all columns present)")
            conn.close()
            return
        
        # Run migrations
        print(f"→ Adding {len(missing_columns)} missing columns...")
        
        for col_name, col_type in missing_columns.items():
            try:
                sql = f"ALTER TABLE survey_responses ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"  ✓ Added column: {col_name} ({col_type})")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f"  → Column {col_name} already exists (skipped)")
                else:
                    print(f"  ✗ Error adding {col_name}: {e}")
                    raise
        
        conn.commit()
        print("✓ Database migration completed successfully")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    # Can be run standalone for manual migration
    print("=== Database Migration Tool ===")
    migrate_database()
    print("=== Migration Complete ===")

