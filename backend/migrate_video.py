import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "eduverse.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(lessons)")
cols = [r[1] for r in cur.fetchall()]
print("Current columns in lessons table:", cols)

if "video_url" not in cols:
    cur.execute("ALTER TABLE lessons ADD COLUMN video_url VARCHAR(500)")
    print("Added video_url column")

if "video_storage_key" not in cols:
    cur.execute("ALTER TABLE lessons ADD COLUMN video_storage_key VARCHAR(255)")
    print("Added video_storage_key column")

conn.commit()

cur.execute("PRAGMA table_info(lessons)")
updated_cols = [r[1] for r in cur.fetchall()]
print("Updated columns in lessons table:", updated_cols)
conn.close()
