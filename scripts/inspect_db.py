import os
import sys
import sqlite3
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def inspect_db(db_name, db_root="mini_dev_databases"):
    db_file = os.path.join(db_root, db_name, f"{db_name}.sqlite")
    if not os.path.exists(db_file):
        print(f"Error: {db_file} not found.")
        return
        
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    print("=" * 60)
    print(f"DATABASE: {db_name}")
    print("=" * 60)
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
    tables = cur.fetchall()
    for name, sql in tables:
        print(f"\n--- TABLE: {name} ---")
        print(sql)
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=str, help="Tên DB cần inspect")
    args = parser.parse_args()
    inspect_db(args.db)
