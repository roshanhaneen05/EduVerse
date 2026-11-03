import sqlite3

def check():
    conn = sqlite3.connect("data/eduverse.db")
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print("Database Tables Found:")
    for t in tables:
        print(f"  - {t}")
    print("\nRecord Counts:")
    for t in tables:
        if not t.startswith("sqlite"):
            cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  {t:25}: {cnt} rows")

    # Check assignment table columns
    cur.execute("PRAGMA table_info(assignments)")
    cols = cur.fetchall()
    print("\nColumns in 'assignments':")
    for col in cols:
        print(f"  {col[1]} ({col[2]}) - NotNull: {col[3]}, PK: {col[5]}")

    # Check assignment_submissions table columns
    cur.execute("PRAGMA table_info(assignment_submissions)")
    cols = cur.fetchall()
    print("\nColumns in 'assignment_submissions':")
    for col in cols:
        print(f"  {col[1]} ({col[2]}) - NotNull: {col[3]}, PK: {col[5]}")

if __name__ == "__main__":
    check()

