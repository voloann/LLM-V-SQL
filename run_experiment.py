import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Thêm root vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation"))
import config
from sql_utils import count_joins, format_view_schema_header
from v_sql_pipeline_LLM import run_v_sql_inference, run_direct_baseline_inference
from evaluation.evaluation_ex import evaluate_ex
from evaluation.evaluation_em import evaluate_em

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def load_db_configs(db_root=config.DB_ROOT, views_dir="views", view_mode="manual", schema_mode="names"):
    """
    Nạp sẵn thông tin schema và view của các DB để tối ưu tốc độ suy luận.
    """
    db_configs = {}
    dbs = [d for d in os.listdir(db_root) if os.path.isdir(os.path.join(db_root, d))]
    
    for d in dbs:
        db_file = os.path.join(db_root, d, f"{d}.sqlite")
        if not os.path.exists(db_file):
            continue
            
        import sqlite3
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
        tables_ddl = [row[0] for row in cur.fetchall()]
        conn.close()
        
        table_schemas = "\n\n".join(tables_ddl)
        
        # Đọc views json (ưu tiên views/<view_mode>/<d>.json rồi đến views/<d>.json)
        view_data = {}
        view_json_path = os.path.join(views_dir, view_mode, f"{d}.json")
        if not os.path.exists(view_json_path):
            view_json_path = os.path.join(views_dir, f"{d}.json")
            
        if os.path.exists(view_json_path):
            with open(view_json_path, "r", encoding="utf-8") as f:
                view_data = json.load(f)
                
        parsed_views = view_data.get("views", [])
        view_schema_header = format_view_schema_header(parsed_views)
        view_mapping_rules = "\n\n".join(v["create_sql"] for v in parsed_views if v.get("create_sql"))
        
        db_configs[d] = {
            "db_id": d,
            "db_file": db_file,
            "table_schemas": table_schemas,
            "parsed_views": parsed_views,
            "view_schema": view_schema_header,
            "view_mapping_rules": view_mapping_rules
        }

        if schema_mode == "described":
            from schema_describe import format_tables_described, format_view_schema_described, load_column_docs
            docs = load_column_docs(db_root, d)
            db_configs[d]["view_schema"] = format_view_schema_described(parsed_views, docs)
            db_configs[d]["direct_schema"] = format_tables_described(table_schemas, docs)

    return db_configs

def run_experiment(
    method="vsql",
    view_mode="manual",
    target_db="all",
    limit=None,
    data_path=config.DATA_PATH,
    output_dir=None,
    resume=True,
    run_eval=True,
    schema_mode="names"
):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    scope_str = target_db if target_db != "all" else "full"
    run_id = f"{timestamp}_{method}_{view_mode}_{scope_str}"
    
    if output_dir is None:
        output_dir = os.path.join("outputs", run_id)
        
    os.makedirs(output_dir, exist_ok=True)
    trace_path = os.path.join(output_dir, "trace.jsonl")
    pred_path = os.path.join(output_dir, "predict.json")
    metrics_path = os.path.join(output_dir, "metrics.json")
    
    print("=" * 70)
    print(f"🚀 BẮT ĐẦU THỰC NGHIỆM: {run_id}")
    print(f"  • Phương pháp: {method.upper()} | View Mode: {view_mode}")
    print(f"  • Database: {target_db} | Giới hạn: {limit or 'Tất cả'}")
    print(f"  • Thư mục kết quả: {output_dir}")
    print("=" * 70)

    # 1. Nạp Dataset
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if target_db != "all":
        data = [d for d in data if d.get("db_id") == target_db]
    if limit is not None:
        data = data[:int(limit)]
        
    print(f"[+] Tổng số câu hỏi cần thực nghiệm: {len(data)}")

    # 2. Xử lý Resume nếu có file trace cũ
    completed_qids = set()
    predictions = {}
    if resume and os.path.exists(trace_path):
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    completed_qids.add(str(item["question_id"]))
                    predictions[str(item["question_id"])] = f"{item['final_sql']}\t{item['db_id']}"
        print(f"[*] Tìm thấy {len(completed_qids)} câu đã hoàn thành từ phiên trước. Bỏ qua các câu này.")

    # 3. Nạp cấu hình DB
    print("[*] Đang nạp cấu hình và schema các CSDL...")
    db_configs = load_db_configs(view_mode=view_mode, schema_mode=schema_mode)

    # 4. Vòng lặp suy luận
    trace_file = open(trace_path, "a", encoding="utf-8")
    
    start_total_time = time.time()
    for idx, item in enumerate(data):
        q_id = str(item.get("question_id"))
        if q_id in completed_qids:
            continue
            
        db_id = item.get("db_id")
        question = item.get("question")
        evidence = item.get("evidence", "")
        difficulty = item.get("difficulty", "simple")
        gold_sql = item.get("SQL", "")
        
        db_cfg = db_configs.get(db_id)
        if not db_cfg:
            print(f"[-] Bỏ qua QID {q_id}: Không tìm thấy DB {db_id}")
            continue

        print(f"\n[{idx+1}/{len(data)}] Xử lý QID {q_id} ({db_id} - {difficulty})...", flush=True)
        print(f"  Q: {question[:85]}...", flush=True)

        if method == "vsql":
            dummy_sql, final_sql, trace_info = run_v_sql_inference(question, db_cfg, evidence)
            print(f"  -> Dummy SQL (Stage 1 | JOINs: {trace_info['stage1']['joins']}): {dummy_sql[:75]}...", flush=True)
            print(f"  -> Final SQL (Stage 2 | JOINs: {trace_info['stage2']['joins']}): {final_sql[:75]}...", flush=True)
            if trace_info['stage2'].get('view_leak'):
                print(f"  [!] CẢNH BÁO: Phát hiện view_leak trong final SQL!", flush=True)
        else: # direct baseline
            dummy_sql = ""
            final_sql, trace_info = run_direct_baseline_inference(question, db_cfg, evidence)
            print(f"  -> Direct SQL (JOINs: {trace_info['joins']}): {final_sql[:75]}...", flush=True)

        predictions[q_id] = f"{final_sql}\t{db_id}"

        # Ghi trace record
        record = {
            "question_id": int(q_id),
            "db_id": db_id,
            "difficulty": difficulty,
            "question": question,
            "evidence": evidence,
            "method": method,
            "final_sql": final_sql,
            "gold_sql": gold_sql,
            "gold_joins": count_joins(gold_sql),
            "trace": trace_info,
            "timestamp": time.time()
        }
        trace_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        trace_file.flush()

    trace_file.close()
    elapsed = time.time() - start_total_time
    print(f"\n[+] Hoàn tất quá trình suy luận! Thời gian: {elapsed:.2f}s")

    # Lưu predict.json
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    print(f"[+] Đã lưu predictions vào: {pred_path}")

    # 5. Đánh giá tự động nếu cờ run_eval = True
    if run_eval and len(predictions) > 0:
        print("\n" + "=" * 70)
        print("🎯 TIẾN HÀNH ĐÁNH GIÁ KẾT QUẢ THỰC NGHIỆM")
        print("=" * 70)
        
        # Tạo tập ground truth tương ứng nếu target_db != all hoặc limit
        eval_gt_path = os.path.join(output_dir, "eval_ground_truth.json")
        with open(eval_gt_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Tính EX
        ex_results = evaluate_ex(
            predicted_sql_path=pred_path,
            ground_truth_path=eval_gt_path,
            db_root_path=config.DB_ROOT,
            num_cpus=1
        )

        # Tính EM
        em_results = evaluate_em(
            predicted_sql_path=pred_path,
            ground_truth_path=eval_gt_path,
            output_log_path=os.path.join(output_dir, "em_details.json")
        )

        # Tổng hợp metrics
        summary_metrics = {
            "run_id": run_id,
            "method": method,
            "view_mode": view_mode,
            "scope": target_db,
            "num_queries": len(data),
            "model": config.SELECTED_MODEL,
            "EX": {
                "simple": ex_results["simple_acc"],
                "moderate": ex_results["moderate_acc"],
                "challenging": ex_results["challenging_acc"],
                "total": ex_results["all_acc"]
            },
            "EM_strict": em_results["strict"],
            "EM_normalized": em_results["normalized"]
        }

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(summary_metrics, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Đã lưu toàn bộ metrics vào: {metrics_path}")

    return run_id, output_dir

def main():
    parser = argparse.ArgumentParser(description="Chạy thực nghiệm V-SQL hoặc Baseline Direct")
    parser.add_argument("--method", choices=["vsql", "direct"], default="vsql", help="Phương pháp suy luận")
    parser.add_argument("--view-mode", choices=["manual", "auto", "fk", "gold", "paper"], default="manual", help="Chế độ view: manual, auto, fk (mở rộng theo khóa ngoại), gold (mọi join trong gold SQL) hoặc paper (gold chọn lọc theo bài báo)")
    parser.add_argument("--db", type=str, default="all", help="Tên database cụ thể hoặc 'all'")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số câu hỏi")
    parser.add_argument("--data", type=str, default=config.DATA_PATH, help="Đường dẫn file dataset")
    parser.add_argument("--output-dir", type=str, default=None, help="Thư mục xuất kết quả")
    parser.add_argument("--no-resume", action="store_true", help="Không đọc lại file trace cũ")
    parser.add_argument("--no-eval", action="store_true", help="Không chạy đánh giá sau khi suy luận")
    parser.add_argument("--schema-mode", choices=["names", "described"], default="names", help="Schema cho Stage 1 và Direct: chỉ tên cột hoặc thêm kiểu dữ liệu và mô tả cột")
    args = parser.parse_args()

    run_experiment(
        method=args.method,
        view_mode=args.view_mode,
        target_db=args.db,
        limit=args.limit,
        data_path=args.data,
        output_dir=args.output_dir,
        resume=(not args.no_resume),
        run_eval=(not args.no_eval),
        schema_mode=args.schema_mode
    )

if __name__ == "__main__":
    main()
