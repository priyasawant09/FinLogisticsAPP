# create_created_at_column.py

import sqlite3
import os
import sys
from pathlib import Path
# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
DB_PATH = "financial_app.db"   # <-- change this if your DB file has a different name/location

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file '{DB_PATH}' not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🔍 Checking if 'created_at' column exists in 'users' table...")

    if not column_exists(cursor, "users", "created_at"):
        print("⏳ Adding 'created_at' column...")
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN created_at DATETIME
        """)
        conn.commit()
        print("✅ Column added.")
    else:
        print("✔ 'created_at' column already exists.")

    print("🔧 Updating existing NULL values with CURRENT_TIMESTAMP...")
    cursor.execute("""
        UPDATE users
        SET created_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL
    """)
    conn.commit()

    print("🎉 Migration complete. Database updated successfully!")

    conn.close()


if __name__ == "__main__":
    main()
