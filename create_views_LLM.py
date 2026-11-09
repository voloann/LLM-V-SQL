import os
import json
import sqlite3
import config
from prompts import get_view_creation_prompt
from llm_client import call_llm, clean_sql
from sql_utils import parse_views_from_sql, format_view_schema_header

def get_db_schema(sqlite_path: str) -> str:
    """Đọc cấu trúc CREATE TABLE từ SQLite."""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return "\n\n".join([t[0] for t in tables if t[0] is not None])

def generate_view_rules_for_db(db_id: str, sqlite_path: str) -> dict:
    """Tạo view mapping rules qua LLM hoặc từ file manual nếu có sẵn."""
    raw_schema = get_db_schema(sqlite_path)
    
    # 1. Kiểm tra xem có file view manual viết tay không
    manual_sql_path = os.path.join(config.VIEWS_DIR, "manual", f"{db_id}.sql")
    if os.path.exists(manual_sql_path):
        print(f"[*] Sử dụng file manual view cho DB '{db_id}': {manual_sql_path}")
        with open(manual_sql_path, "r", encoding="utf-8") as f:
            views_sql = f.read().strip()
    else:
        # 2. Sinh tự động qua LLM
        prompt = get_view_creation_prompt(raw_schema)
        views_sql, stats = call_llm(
            prompt=prompt,
            temperature=config.TEMPERATURE,
            max_tokens=1000
        )
        if stats.get("error"):
            print(f"[!] Lỗi kết nối LLM cho DB {db_id}: {stats['error']}")
            views_sql = ""

    # 3. Trích xuất chính xác cấu trúc view bằng sqlglot (Task T1.4)
    parsed_views = parse_views_from_sql(views_sql)
    if parsed_views:
        view_schema_header = format_view_schema_header(parsed_views)
    else:
        # Fallback nếu parse lỗi hoặc chuỗi rỗng
        view_schema_header = views_sql if views_sql else f"v_{db_id}"

    return {
        "view_schema": view_schema_header,
        "view_mapping_rules": views_sql,
        "table_schemas": raw_schema,
        "parsed_views": parsed_views
    }

def build_view_mappings():
    db_root = config.DB_ROOT
    out_file = os.path.join(config.DATA_DIR, "view_mappings.json")
    os.makedirs(config.DATA_DIR, exist_ok=True)

    existing_mappings = {}
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                existing_mappings = json.load(f)
            print(f"[*] Đã có sẵn mapping của {len(existing_mappings)} database.")
        except Exception:
            existing_mappings = {}

    if not os.path.exists(db_root):
        print(f"[!] Không tìm thấy thư mục {db_root}!")
        return existing_mappings

    db_names = [d for d in os.listdir(db_root) if os.path.isdir(os.path.join(db_root, d))]
    for db_id in db_names:
        if db_id in existing_mappings and existing_mappings[db_id].get("view_mapping_rules"):
            print(f"[SKIP] DB '{db_id}' đã có mapping.")
            continue

        sqlite_file = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(sqlite_file):
            continue

        print(f"[CREATE] Đang tạo view mapping cho DB '{db_id}'...")
        mapping_data = generate_view_rules_for_db(db_id, sqlite_file)
        existing_mappings[db_id] = mapping_data

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(existing_mappings, f, indent=4)

    return existing_mappings

if __name__ == "__main__":
    build_view_mappings()