import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
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
    global exec_result
    exec_result = []
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

def load_and_align_data(pred_path, gt_path, db_root_path):
    """
    Khớp nối câu hỏi dự đoán và ground truth chính xác tuyệt đối theo question_id.
    Tránh lỗi lệch thứ tự, lệch số lượng hoặc mất câu hỏi.
    Nếu một câu hỏi thiếu dự đoán, sẽ gán pred_sql = '' (kết quả thực thi = 0).
    """
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    with open(pred_path, "r", encoding="utf-8") as f:
        pred_data = json.load(f)

    pred_dict = {}
    if isinstance(pred_data, dict):
        for k, v in pred_data.items():
            val = str(v).strip()
            sql = val.split("\t")[0].strip() if "\t" in val else val
            pred_dict[str(k).strip()] = sql
    elif isinstance(pred_data, list):
        for item in pred_data:
            if isinstance(item, dict):
                q_id = str(item.get("question_id", "")).strip()
                sql = item.get("predict", item.get("SQL", "")).strip()
                if q_id:
                    pred_dict[q_id] = sql

    query_pairs = []
    db_paths_gt = []
    difficulties = []
    q_ids = []

    for item in gt_data:
        q_id = str(item.get("question_id", "")).strip()
        db_id = item.get("db_id", "").strip()
        gold_sql = item.get("SQL", "").strip()
        diff = item.get("difficulty", "simple").strip().lower()

        pred_sql = pred_dict.get(q_id, "")
        db_path = os.path.join(db_root_path, db_id, f"{db_id}.sqlite")

        query_pairs.append((pred_sql, gold_sql))
        db_paths_gt.append(db_path)
        difficulties.append(diff)
        q_ids.append(q_id)

    return query_pairs, db_paths_gt, difficulties, q_ids

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

def evaluate_ex(predicted_sql_path, ground_truth_path, db_root_path, num_cpus=1, meta_time_out=30.0, sql_dialect="SQLite", output_log_path=""):
    query_pairs, db_paths_gt, difficulties, q_ids = load_and_align_data(
        predicted_sql_path, ground_truth_path, db_root_path
    )

    run_sqls_parallel(
        query_pairs,
        db_places=db_paths_gt,
        num_cpus=num_cpus,
        meta_time_out=meta_time_out,
        sql_dialect=sql_dialect,
    )

    sorted_results = sort_results(exec_result)

    simple_acc, moderate_acc, challenging_acc, all_acc, count_lists = compute_acc_by_diff(
        sorted_results, difficulties
    )
    score_lists = [simple_acc, moderate_acc, challenging_acc, all_acc]

    print("\n--- CALCULATING EX RESULTS ---")
    print_data(score_lists, count_lists, metric="EX", result_log_file=output_log_path if output_log_path else None)
    print("===========================================================================================")
    print(f"Finished EX evaluation for {sql_dialect} on Mini Dev")

    return {
        "simple_acc": simple_acc,
        "moderate_acc": moderate_acc,
        "challenging_acc": challenging_acc,
        "all_acc": all_acc,
        "counts": count_lists,
        "detailed_results": [{"q_id": q_ids[i], "res": sorted_results[i]["res"]} for i in range(len(sorted_results))]
    }

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

    evaluate_ex(
        predicted_sql_path=args.predicted_sql_path,
        ground_truth_path=args.ground_truth_path,
        db_root_path=args.db_root_path,
        num_cpus=args.num_cpus,
        meta_time_out=args.meta_time_out,
        sql_dialect=args.sql_dialect,
        output_log_path=args.output_log_path,
    )