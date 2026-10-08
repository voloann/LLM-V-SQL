import json
import os
import sqlite3
import subprocess
import re
from create_views_LLM import build_view_mappings
from v_sql_pipeline_LLM import run_v_sql_inference

def execute_sqlite_query(db_path: str, sql_query: str):
    """Thực thi câu SQL trên SQLite và trả về kết quả (tối đa 5 dòng xem trước)."""
    if not os.path.exists(db_path):
        return f"[!] Không tìm thấy file CSDL: {db_path}"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "[] (Kết quả rỗng)"
        # Giới hạn in tối đa 5 dòng để không bị tràn màn hình
        preview = rows[:5]
        suffix = f" ... (Tổng {len(rows)} dòng)" if len(rows) > 5 else f" (Tổng {len(rows)} dòng)"
        return f"{preview}{suffix}"
    except Exception as e:
        return f"[Lỗi thực thi SQLite]: {e}"

def clean_sql_string(text: str) -> str:
    """Loại bỏ thẻ <think>...</think> (nếu dùng model thinking) và markdown thừa."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "```sql" in text:
        text = text.split("```sql")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return " ".join(text.replace("\t", " ").replace("\n", " ").split())

def main():
    data_path = "data/Test.json"
    pred_path = "predict_dev.json"
    db_root_path = "mini_dev_databases"
    eval_script = "evaluation/evaluation_ex.py"

    if not os.path.exists(data_path):
        print(f"[!] Không tìm thấy file dữ liệu: {data_path}")
        return

    # 1. Kiểm tra và in Table Mapping
    print("--- KIỂM TRA BỘ TABLE MAPPINGS (LM STUDIO) ---")
    views_dict = build_view_mappings()
    print(f"[*] Đã có sẵn mapping của {len(views_dict)} database.")
    
    for db_name, cfg in views_dict.items():
        print(f"\n[+] Table Mapping cho DB '{db_name}':")
        mapping_rule = cfg.get("view_mapping_rules", "").strip()
        print(mapping_rule if mapping_rule else "(Chưa có mapping rule)")
    print("-" * 50)

    # 2. Đọc file câu hỏi kiểm thử
    with open(data_path, "r", encoding="utf-8") as f:
        ground_truth_list = json.load(f)

    print(f"\n=== BẮT ĐẦU CHẠY V-SQL VỚI LM STUDIO ({len(ground_truth_list)} câu) ===")
    predictions = {}

    for idx, item in enumerate(ground_truth_list):
        q_id = str(item["question_id"])
        db_id = item["db_id"]
        question = item["question"]
        
        # Bốc tách evidence từ dataset (hỗ trợ cả key 'evidence' hoặc 'hint')
        evidence = item.get("evidence", "") or item.get("hint", "")
        
        gold_sql = item.get("SQL", "")
        db_file = os.path.join(db_root_path, db_id, f"{db_id}.sqlite")

        print(f"\n[Câu hỏi {idx + 1}/{len(ground_truth_list)} - ID: {q_id}] DB: {db_id}")
        print(f"User Query: {question}")
        if evidence:
            print(f"Evidence  : {evidence}")

        db_cfg = views_dict.get(db_id, {})
        
        # Chạy quy trình 2 Stage của V-SQL kèm tham số evidence
        dummy_sql, final_sql = run_v_sql_inference(question, db_cfg, evidence=evidence)

        # Làm sạch chuỗi SQL
        dummy_sql_clean = clean_sql_string(dummy_sql)
        final_sql_clean = clean_sql_string(final_sql)

        # Hiển thị kết quả Stage 1 và Stage 2
        print(f"Stage 1 (Dummy SQL): {dummy_sql_clean}")
        print(f"Stage 2 (Final SQL): {final_sql_clean}")

        # Thực thi câu lệnh trực tiếp trên SQLite và in kết quả
        print("\n--- KẾT QUẢ THỰC THI TRÊN SQLITE ---")
        pred_res = execute_sqlite_query(db_file, final_sql_clean)
        gold_res = execute_sqlite_query(db_file, gold_sql)
        print(f"-> Predicted Result : {pred_res}")
        print(f"-> Gold SQL Result  : {gold_res}")
        print("-" * 50)

        # Định dạng chuẩn bắt buộc của file đánh giá BIRD: "{SQL}\t{db_id}"
        predictions[q_id] = f"{final_sql_clean}\t{db_id}"

    # 3. Ghi file kết quả
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=4)
    print(f"\n[+] Đã lưu kết quả vào: {pred_path}")

    # 4. Kích hoạt script đánh giá EX
    if os.path.exists(eval_script):
        print("\n=== BẮT ĐẦU ĐÁNH GIÁ EXECUTION ACCURACY (EX) ===")
        with open(eval_script, "r", encoding="utf-8") as f:
            eval_code = f.read()
        gt_arg = "--ground_truth_path" if "--ground_truth_path" in eval_code else "--ground_truth_sql_path"

        cmd = [
            "python", eval_script,
            "--db_root_path", db_root_path,
            "--predicted_sql_path", pred_path,
            gt_arg, data_path,
            "--num_cpus", "4",
            "--meta_time_out", "30.0"
        ]
        subprocess.run(cmd)
    else:
        print(f"\n[!] Không tìm thấy script {eval_script}")

if __name__ == "__main__":
    main()