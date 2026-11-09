import os
import sys
import json
import argparse
from collections import defaultdict

# Thêm root vào sys.path để import sql_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sql_utils import canonical_sql

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def normalize_strict(sql: str) -> str:
    """Chuẩn hoá tối thiểu cho EM-strict: bỏ chấm phẩy, khoảng trắng thừa, lowercase."""
    if not sql:
        return ""
    return " ".join(sql.strip().rstrip(";").lower().split())

def evaluate_em(predicted_sql_path: str, ground_truth_path: str, output_log_path: str = "") -> dict:
    """
    Tính Exact Match (EM) ở 2 mức độ:
    1. EM-strict: So sánh chuỗi trực tiếp sau khi chuẩn hoá khoảng trắng & chữ hoa/thường.
    2. EM-normalized: So sánh cây cú pháp đã chuẩn hoá (canonical AST qua sqlglot, khử alias).
    Đồng thời thống kê tỉ lệ parse error (T4.3).
    """
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    with open(predicted_sql_path, "r", encoding="utf-8") as f:
        pred_data = json.load(f)

    # Chuyển predictions về dạng dict {question_id: pred_sql}
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

    strict_results = defaultdict(list)
    norm_results = defaultdict(list)
    parse_errors = 0
    total_queries = len(gt_data)
    details = []

    for item in gt_data:
        q_id = str(item.get("question_id", "")).strip()
        diff = item.get("difficulty", "simple").strip().lower()
        gold_sql = item.get("SQL", "").strip()
        pred_sql = pred_dict.get(q_id, "").strip()

        # 1. EM-strict
        em_strict = int(normalize_strict(pred_sql) == normalize_strict(gold_sql)) if (pred_sql and gold_sql) else 0

        # 2. EM-normalized
        em_norm = 0
        is_parse_err = False
        if pred_sql and gold_sql:
            try:
                c_pred = canonical_sql(pred_sql)
                c_gold = canonical_sql(gold_sql)
                em_norm = int(c_pred == c_gold)
            except Exception:
                parse_errors += 1
                is_parse_err = True
                em_norm = em_strict

        strict_results[diff].append(em_strict)
        strict_results["all"].append(em_strict)

        norm_results[diff].append(em_norm)
        norm_results["all"].append(em_norm)

        details.append({
            "question_id": q_id,
            "difficulty": diff,
            "em_strict": em_strict,
            "em_norm": em_norm,
            "parse_error": is_parse_err
        })

    def calc_pct(lst):
        return round(sum(lst) / len(lst) * 100, 2) if lst else 0.0

    metrics = {
        "total_queries": total_queries,
        "parse_errors": parse_errors,
        "parse_error_pct": round(parse_errors / total_queries * 100, 2) if total_queries else 0.0,
        "strict": {
            "simple": calc_pct(strict_results["simple"]),
            "moderate": calc_pct(strict_results["moderate"]),
            "challenging": calc_pct(strict_results["challenging"]),
            "all": calc_pct(strict_results["all"]),
        },
        "normalized": {
            "simple": calc_pct(norm_results["simple"]),
            "moderate": calc_pct(norm_results["moderate"]),
            "challenging": calc_pct(norm_results["challenging"]),
            "all": calc_pct(norm_results["all"]),
        },
        "counts": {
            "simple": len(strict_results["simple"]),
            "moderate": len(strict_results["moderate"]),
            "challenging": len(strict_results["challenging"]),
            "all": total_queries
        }
    }

    # In bảng kết quả
    print("\n" + "=" * 70)
    print("🎯 BẢNG KẾT QUẢ EXACT MATCH (EM)")
    print("=" * 70)
    print(f"{'Difficulty':<15} | {'Count':<8} | {'EM-Strict (%)':<15} | {'EM-Normalized (%)':<18}")
    print("-" * 70)
    for d in ["simple", "moderate", "challenging"]:
        cnt = metrics["counts"][d]
        st = metrics["strict"][d]
        nm = metrics["normalized"][d]
        print(f"{d.capitalize():<15} | {cnt:<8} | {st:<15.2f} | {nm:<18.2f}")
    print("-" * 70)
    print(f"{'TOTAL':<15} | {metrics['counts']['all']:<8} | {metrics['strict']['all']:<15.2f} | {metrics['normalized']['all']:<18.2f}")
    print(f"Parse Errors (fallback): {parse_errors}/{total_queries} ({metrics['parse_error_pct']}%)")
    print("=" * 70)

    if output_log_path:
        os.makedirs(os.path.dirname(output_log_path), exist_ok=True)
        with open(output_log_path, "w", encoding="utf-8") as f:
            json.dump({"metrics": metrics, "details": details}, f, indent=2)

    return metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Danh gia Exact Match (EM)")
    parser.add_argument("--predicted_sql_path", type=str, required=True)
    parser.add_argument("--ground_truth_path", type=str, required=True)
    parser.add_argument("--output_log_path", type=str, default="")
    args = parser.parse_args()

    evaluate_em(args.predicted_sql_path, args.ground_truth_path, args.output_log_path)
