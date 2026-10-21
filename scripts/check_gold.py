import json
import os
import sqlite3
import sys
from func_timeout import func_timeout, FunctionTimedOut

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def execute_single_query(db_file, sql):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(sql)
    _ = cursor.fetchall()
    conn.close()

def check_gold_queries(data_path="data/mini_dev_sqlite.json", db_root="mini_dev_databases", timeout_sec=10):
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return False
        
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total = len(data)
    available = 0
    passed = 0
    failed = []
    timeouts = []
    missing_dbs = set()
    
    print(f"Starting execution check on {total} queries (timeout={timeout_sec}s per query)...")
    for idx, item in enumerate(data):
        q_id = item.get("question_id")
        db_id = item.get("db_id")
        sql = item.get("SQL")
        
        db_file = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_file):
            missing_dbs.add(db_id)
            continue
            
        available += 1
        try:
            func_timeout(timeout_sec, execute_single_query, args=(db_file, sql))
            passed += 1
        except FunctionTimedOut:
            timeouts.append((q_id, db_id, sql, f"Timeout > {timeout_sec}s"))
        except Exception as e:
            failed.append((q_id, db_id, sql, str(e)))

        if (idx + 1) % 50 == 0 or (idx + 1) == total:
            print(f"  Progress: {idx + 1}/{total} checked ({passed} passed, {len(failed)} failed, {len(timeouts)} timeouts)...", flush=True)
            
    print("\n" + "=" * 50)
    print("=== CHECK GOLD SQL QUERIES SUMMARY ===")
    print("=" * 50)
    print(f"Total dataset queries: {total}")
    print(f"Available DB queries:  {available}/{total}")
    print(f"Passed execution:      {passed}/{available}")
    print(f"Timeouts (> {timeout_sec}s):     {len(timeouts)}")
    print(f"Failed syntax/logic:   {len(failed)}")
    if missing_dbs:
        print(f"Databases missing ({len(missing_dbs)}): {sorted(missing_dbs)}")
    if failed:
        print(f"\nFailed queries details ({len(failed)}):")
        for q_id, db_id, sql, err in failed[:5]:
            print(f"  [QID {q_id} | {db_id}] Error: {err}")
    if timeouts:
        print(f"\nTimed out queries details ({len(timeouts)}):")
        for q_id, db_id, sql, err in timeouts[:5]:
            print(f"  [QID {q_id} | {db_id}] {err}")
    if not failed and not timeouts and available == total:
        print("\nAll 500 gold queries executed successfully!")
        
    return len(failed) == 0 and available == total

if __name__ == "__main__":
    check_gold_queries()
