import sqlite3

conn = sqlite3.connect('tracker.db')
c = conn.cursor()

# Try to add the new column to the existing table
try:
    c.execute("ALTER TABLE users ADD COLUMN premium_status TEXT DEFAULT 'Standard'")
    conn.commit()
    print("Column successfully added without losing data!")
except sqlite3.OperationalError as e:
    # If the column already exists, SQLite will safely ignore it
    print(f"Skipped: {e}")

conn.close()
