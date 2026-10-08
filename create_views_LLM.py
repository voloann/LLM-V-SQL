# create_views.py
import os
import json
import sqlite3
from openai import OpenAI
from prompts import get_view_creation_prompt
from config import SELECTED_MODEL

# Kết nối Local Server của LM Studio
LM_STUDIO_URL = "http://localhost:1234/v1"
client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

def get_db_schema(sqlite_path: str) -> str:
    """Đọc cấu trúc CREATE TABLE từ SQLite."""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return "\n\n".join([t[0] for t in tables if t[0] is not None])

def clean_sql(text: str) -> str:
    if "```sql" in text:
        text = text.split("```sql")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()

def generate_view_rules_for_db(db_id: str, sqlite_path: str) -> dict:
    raw_schema = get_db_schema(sqlite_path)
    prompt = get_view_creation_prompt(raw_schema)
    
    try:
        response = client.chat.completions.create(
            model=SELECTED_MODEL,  # LM Studio tự động nhận diện model đang nạp
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )
        views_sql = clean_sql(response.choices[0].message.content)
        
        # Trích xuất header cột cho view_schema để tiết kiệm context
        try:
            view_schema_header = views_sql.split("FROM")[0].split("from")[0].strip()
        except Exception:
            view_schema_header = views_sql

        return {
            "view_schema": view_schema_header,
            "view_mapping_rules": views_sql,
            "table_schemas": raw_schema
        }
    except Exception as e:
        print(f"[!] Lỗi kết nối LM Studio cho DB {db_id}: {e}")
        return {
            "view_schema": f"View v_{db_id}",
            "view_mapping_rules": "",
            "table_schemas": raw_schema
        }

def build_view_mappings():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_root = os.path.join(base_dir, "mini_dev_databases")
    out_file = os.path.join(base_dir, "data", "view_mappings.json")
    os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)

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

        print(f"[CREATE] Đang tạo view mapping cho DB '{db_id}' qua LM Studio...")
        mapping_data = generate_view_rules_for_db(db_id, sqlite_file)
        existing_mappings[db_id] = mapping_data

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(existing_mappings, f, indent=4)

    return existing_mappings

if __name__ == "__main__":
    build_view_mappings()