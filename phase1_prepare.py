import os
import sys
import json
import shutil
import sqlite3
import hashlib
import tempfile
import argparse
from pathlib import Path

# Thêm root vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DB_ROOT, VIEW_MODE, SELECTED_MODEL
from sql_utils import parse_views_from_sql
from prompts import get_view_creation_prompt as get_table_mapping_prompt
from llm_client import call_llm

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def compute_file_hash(filepath: str) -> str:
    """Tính SHA256 để đảm bảo file DB gốc không bị thay đổi."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def validate_views(db_path: str, views: list[dict]) -> tuple[list[dict], bool]:
    """
    Tạo view trên BẢN SAO SQLite tạm thời, kiểm tra tính hợp lệ và đếm số dòng.
    Đảm bảo 100% không ghi đè hay sửa đổi DB gốc.
    """
    if not os.path.exists(db_path):
        print(f"Error: DB file not found: {db_path}")
        return [], False

    orig_hash = compute_file_hash(db_path)
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, os.path.basename(db_path))
    
    try:
        shutil.copy2(db_path, temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        for v in views:
            v_name = v.get("name")
            create_sql = v.get("create_sql")
            try:
                cursor.execute(f"DROP VIEW IF EXISTS `{v_name}`;")
                cursor.execute(create_sql)
                cursor.execute(f"SELECT COUNT(*) FROM `{v_name}`;")
                count = cursor.fetchone()[0]
                v["valid"] = True
                v["row_count"] = count
                v["error"] = None
            except Exception as e:
                v["valid"] = False
                v["row_count"] = 0
                v["error"] = str(e)
                
        conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    after_hash = compute_file_hash(db_path)
    db_untouched = (orig_hash == after_hash)
    
    return views, db_untouched

def get_database_schema_and_descriptions(db_id: str, db_root: str = DB_ROOT) -> str:
    """Đọc schema DDL và database_description CSV (nếu có)."""
    db_file = os.path.join(db_root, db_id, f"{db_id}.sqlite")
    if not os.path.exists(db_file):
        return ""
        
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
    tables_ddl = [row[0] for row in cur.fetchall()]
    conn.close()
    
    schema_text = "\n\n".join(tables_ddl)
    
    # Kiểm tra database_description CSVs
    desc_dir = os.path.join(db_root, db_id, "database_description")
    desc_texts = []
    if os.path.exists(desc_dir):
        for csv_file in sorted(os.listdir(desc_dir)):
            if csv_file.endswith(".csv"):
                csv_path = os.path.join(desc_dir, csv_file)
                try:
                    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [line.strip() for line in f if line.strip()]
                        if lines:
                            desc_texts.append(f"-- Table Description ({csv_file}):\n" + "\n".join(lines[:10]))
                except Exception:
                    pass
                    
    if desc_texts:
        schema_text += "\n\n# Table Descriptions & Value Previews\n" + "\n\n".join(desc_texts)
        
    return schema_text

def prepare_views_for_db(db_id: str, mode: str = "manual", output_dir: str = "views", db_root: str = DB_ROOT) -> dict:
    """
    Chuẩn bị views cho 1 DB:
    - Mode 'manual': Đọc từ views/manual/<db_id>.sql
    - Mode 'auto': Dùng LLM sinh theo prompt Hình 2
    Sau đó validate trên bản sao SQLite và lưu file views/<db_id>.json.
    """
    db_file = os.path.join(db_root, db_id, f"{db_id}.sqlite")
    if not os.path.exists(db_file):
        print(f"[-] DB {db_id} not found at {db_file}")
        return None

    views_sql = ""
    if mode == "manual":
        manual_sql_path = os.path.join("views", "manual", f"{db_id}.sql")
        if not os.path.exists(manual_sql_path):
            print(f"[-] Manual view file not found: {manual_sql_path}")
            return None
        with open(manual_sql_path, "r", encoding="utf-8") as f:
            views_sql = f.read()
    elif mode == "auto":
        print(f"[*] Calling LLM to generate auto views for {db_id}...")
        schema_desc = get_database_schema_and_descriptions(db_id, db_root)
        prompt = get_table_mapping_prompt(schema_desc)
        views_sql, stats = call_llm(prompt)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Parse các câu lệnh CREATE VIEW
    parsed_views = parse_views_from_sql(views_sql)
    if not parsed_views:
        print(f"[-] No valid CREATE VIEW statements parsed for {db_id}")
        return None

    # Validate trên bản sao SQLite
    validated_views, db_untouched = validate_views(db_file, parsed_views)
    
    valid_count = sum(1 for v in validated_views if v.get("valid"))
    print(f"  [+] DB: {db_id} | Mode: {mode} | Valid views: {valid_count}/{len(validated_views)} | DB safe (untouched): {db_untouched}")

    result_data = {
        "db_id": db_id,
        "mode": mode,
        "db_untouched": db_untouched,
        "views": validated_views
    }

    # Lưu ra views/<db_id>.json và views/<mode>/<db_id>.json
    os.makedirs(output_dir, exist_ok=True)
    mode_dir = os.path.join(output_dir, mode)
    os.makedirs(mode_dir, exist_ok=True)

    dest_file = os.path.join(output_dir, f"{db_id}.json")
    mode_file = os.path.join(mode_dir, f"{db_id}.json")
    
    with open(dest_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    with open(mode_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    return result_data

def main():
    parser = argparse.ArgumentParser(description="Pha 1: Table Mapping & Validate Views")
    parser.add_argument("--mode", choices=["manual", "auto"], default="manual", help="Che do tao view: manual hoac auto")
    parser.add_argument("--db", type=str, default="superhero", help="Ten database (hoac 'all')")
    parser.add_argument("--output-dir", type=str, default="views", help="Thu muc luu views JSON")
    args = parser.parse_args()

    if args.db == "all":
        dbs = sorted([d for d in os.listdir(DB_ROOT) if os.path.isdir(os.path.join(DB_ROOT, d))])
        print(f"Preparing views for ALL {len(dbs)} databases in mode '{args.mode}'...")
        for d in dbs:
            prepare_views_for_db(d, mode=args.mode, output_dir=args.output_dir)
    else:
        prepare_views_for_db(args.db, mode=args.mode, output_dir=args.output_dir)

if __name__ == "__main__":
    main()
