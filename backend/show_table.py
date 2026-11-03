import sqlite3
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

db_path = Path(__file__).resolve().parent / "data" / "eduverse.db"

def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    print("\n--- Available Tables in eduverse.db ---")
    print("-" * 52)
    for i, t in enumerate(tables, 1):
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        count = cur.fetchone()[0]
        print(f"  {i:>2}. {t:<32} ({count} rows)")
    print("-" * 52)
    print("To view data in a table, run:  python show_table.py <table_name>\n")

def show_table(table_name):
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    if not table_name:
        list_tables(conn)
        conn.close()
        return

    # Check table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cur.fetchone():
        print(f"\n[!] Table '{table_name}' does not exist.")
        list_tables(conn)
        conn.close()
        return

    # Get column names
    cur.execute(f'PRAGMA table_info("{table_name}");')
    cols = [col[1] for col in cur.fetchall()]

    # Fetch rows
    cur.execute(f'SELECT * FROM "{table_name}" LIMIT 50;')
    rows = cur.fetchall()

    print(f"\nTABLE: {table_name} ({len(rows)} row(s) displayed)")
    print("=" * 80)

    if not rows:
        print(f"Columns: {', '.join(cols)}")
        print("Table is currently empty (0 rows).")
        print("=" * 80)
        conn.close()
        return

    # Truncate long strings for clean terminal display
    cleaned_rows = []
    for row in rows:
        cleaned_row = []
        for val in row:
            s = str(val) if val is not None else "NULL"
            if len(s) > 28:
                s = s[:25] + "..."
            cleaned_row.append(s)
        cleaned_rows.append(cleaned_row)

    # Determine column widths
    col_widths = [len(c) for c in cols]
    for row in cleaned_rows:
        for idx, val in enumerate(row):
            if len(val) > col_widths[idx]:
                col_widths[idx] = len(val)

    # Print Header
    header = " | ".join(cols[i].ljust(col_widths[i]) for i in range(len(cols)))
    print(header)
    print("-" * len(header))

    # Print Rows
    for row in cleaned_rows:
        line = " | ".join(row[i].ljust(col_widths[i]) for i in range(len(row)))
        print(line)

    print("=" * 80 + "\n")
    conn.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    show_table(target)
