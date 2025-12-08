# migrate_users_add_email_verified.py
import sqlite3

DB_PATH = "financial_app.db"  # adjust if your DB file has a different name

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add email column
try:
    cur.execute("ALTER TABLE users ADD COLUMN email TEXT;")
    print("Added column 'email'")
except Exception as e:
    print("Skipping email column:", e)

# Add is_verified column with default 0 (False)
try:
    cur.execute(
        "ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0;"
    )
    print("Added column 'is_verified'")
except Exception as e:
    print("Skipping is_verified column:", e)    

conn.commit()
conn.close()
print("Migration done.")
