import sys
import os
import json
import argparse
import multiprocessing as mp
from func_timeout import func_timeout, FunctionTimedOut
from evaluation_utils import (
    execute_sql,
    sort_results,
    print_data,
)

exec_result = []

def result_callback(result):
    exec_result.append(result)

def calculate_ex(predicted_res, ground_truth_res):
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res

def execute_model(predicted_sql, ground_truth, db_place, idx, meta_time_out, sql_dialect):
    try:
        res = func_timeout(
            meta_time_out,
            execute_sql,
            args=(predicted_sql, ground_truth, db_place, sql_dialect, calculate_ex),
        )
    except KeyboardInterrupt:
        sys.exit(0)
    except FunctionTimedOut:
        res = 0
    except Exception:
        res = 0
    return {"sql_idx": idx, "res": res}

def run_sqls_parallel(sqls, db_places, num_cpus=1, meta_time_out=30.0, sql_dialect="SQLite"):
    pool = mp.Pool(processes=num_cpus)
    for i, sql_pair in enumerate(sqls):
        predicted_sql, ground_truth = sql_pair
        pool.apply_async(
            execute_model,
            args=(
                predicted_sql,
                ground_truth,
                db_places[i],
                i,
                meta_time_out,
                sql_dialect,
            ),
            callback=result_callback,
        )
    pool.close()
    pool.join()

def load_ground_truth(gt_path, db_root_path):
    """Đọc Ground Truth hỗ trợ cả file JSON gốc lẫn file SQL dạng text."""
    gt_queries = []
    db_paths_gt = []
    difficulties = []

    if gt_path.endswith(".json"):
        with open(gt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            sql = item.get("SQL", "").strip()
            db_id = item.get("db_id", "").strip()
            diff = item.get("difficulty", "simple").strip().lower()

            gt_queries.append(sql)
            db_paths_gt.append(os.path.join(db_root_path, db_id, f"{db_id}.sqlite"))
            difficulties.append(diff)
    else:
        # Xử lý định dạng text: sql \t db_name
        with open(gt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            parts = line_str.split("\t")
            if len(parts) >= 2:
                sql = parts[0].strip()
                db_id = parts[1].strip()
            else:
                sql = parts[0].strip()
                db_id = ""
            gt_queries.append(sql)
            db_paths_gt.append(os.path.join(db_root_path, db_id, f"{db_id}.sqlite"))
            difficulties.append("simple")

    return gt_queries, db_paths_gt, difficulties

def load_predictions(pred_path):
    """Đọc file dự đoán JSON: {question_id: sql + '\t' + db_id} hoặc mảng JSON."""
    pred_queries = []
    with open(pred_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Sắp xếp theo question_id tăng dần để khớp chỉ mục
        sorted_keys = sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else x)
        for k in sorted_keys:
            val = str(data[k]).strip()
            if "\t" in val:
                sql = val.split("\t")[0].strip()
            else:
                sql = val
            pred_queries.append(sql)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                pred_queries.append(item.get("predict", item.get("SQL", "")).strip())
            else:
                pred_queries.append(str(item).split("\t")[0].strip())

    return pred_queries

def compute_acc_by_diff(exec_results, difficulties):
    num_queries = len(exec_results)
    if num_queries == 0:
        return 0.0, 0.0, 0.0, 0.0, [0, 0, 0, 0]

    simple_results = []
    moderate_results = []
    challenging_results = []

    for i, diff in enumerate(difficulties):
        if i >= len(exec_results):
            break
        res_val = exec_results[i]["res"]
        if diff == "simple":
            simple_results.append(res_val)
        elif diff == "moderate":
            moderate_results.append(res_val)
        elif diff == "challenging":
            challenging_results.append(res_val)
        else:
            simple_results.append(res_val)

    simple_acc = (sum(simple_results) / len(simple_results) * 100) if simple_results else 0.0
    moderate_acc = (sum(moderate_results) / len(moderate_results) * 100) if moderate_results else 0.0
    challenging_acc = (sum(challenging_results) / len(challenging_results) * 100) if challenging_results else 0.0
    all_acc = (sum([r["res"] for r in exec_results]) / num_queries * 100)

    count_lists = [
        len(simple_results),
        len(moderate_results),
        len(challenging_results),
        num_queries,
    ]
    return simple_acc, moderate_acc, challenging_acc, all_acc, count_lists

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument("--predicted_sql_path", type=str, required=True)
    args_parser.add_argument("--ground_truth_path", type=str, required=True)
    args_parser.add_argument("--db_root_path", type=str, required=True)
    args_parser.add_argument("--num_cpus", type=int, default=1)
    args_parser.add_argument("--meta_time_out", type=float, default=30.0)
    args_parser.add_argument("--diff_json_path", type=str, default="")
    args_parser.add_argument("--sql_dialect", type=str, default="SQLite")
    args_parser.add_argument("--output_log_path", type=str, default="")
    args = args_parser.parse_args()

    exec_result = []

    # 1. Đọc dữ liệu dự đoán và ground truth an toàn
    pred_queries = load_predictions(args.predicted_sql_path)
    gt_queries, db_paths_gt, difficulties = load_ground_truth(args.ground_truth_path, args.db_root_path)

    # Đảm bảo số lượng 2 bên bằng nhau
    min_len = min(len(pred_queries), len(gt_queries))
    pred_queries = pred_queries[:min_len]
    gt_queries = gt_queries[:min_len]
    db_paths_gt = db_paths_gt[:min_len]
    difficulties = difficulties[:min_len]

    query_pairs = list(zip(pred_queries, gt_queries))

    # 2. Chạy so sánh kết quả thực thi
    run_sqls_parallel(
        query_pairs,
        db_places=db_paths_gt,
        num_cpus=args.num_cpus,
        meta_time_out=args.meta_time_out,
        sql_dialect=args.sql_dialect,
    )

    exec_result = sort_results(exec_result)

    print("\n--- BẮT ĐẦU TÍNH TOÁN KẾT QUẢ EX ---")
    simple_acc, moderate_acc, challenging_acc, all_acc, count_lists = compute_acc_by_diff(
        exec_result, difficulties
    )
    score_lists = [simple_acc, moderate_acc, challenging_acc, all_acc]

    print_data(score_lists, count_lists, metric="EX", result_log_file=args.output_log_path if args.output_log_path else None)
    print("===========================================================================================")
    print(f"Hoàn thành đánh giá EX cho {args.sql_dialect} trên tập Mini Dev")
    print("\n")