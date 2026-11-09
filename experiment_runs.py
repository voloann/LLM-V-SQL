"""Catalog of the experiment runs behind the report, in the order they were done, with normalized metrics."""
import functools
import json
import os

import config
from evaluation.evaluation_em import normalize_strict
from sql_utils import canonical_sql

MAIN_RUNS = ("qwen3_4b_500_paper", "qwen7b_500_paper", "qwen32b_500_paper", "luna_500_paper")
LEVELS = (("simple", "Simple"), ("moderate", "Moderate"), ("challenging", "Challenging"))

CATALOG = [
    {
        "key": "stored_7b",
        "title": "Kết quả lưu ban đầu",
        "model": "Qwen2.5-Coder 7B",
        "view_mode": "manual",
        "schema_mode": "names",
        "source": "stored_metrics",
        "why": "Điểm xuất phát: Direct cao hơn V-SQL, trái với kỳ vọng ban đầu.",
        "finding": "Điểm V-SQL bị thổi lên vì superhero.sqlite còn sót view, nên SQL cuối còn tên view vẫn chạy được khi chấm.",
        "valid": False,
        "n": 500,
        "cost_usd": 0,
    },
    {
        "key": "rescored_7b",
        "title": "Chấm lại trên bảng gốc",
        "model": "Qwen2.5-Coder 7B",
        "view_mode": "manual",
        "schema_mode": "names",
        "source": "run",
        "metrics_dir": "rescored_physical",
        "direct_trace": "500_all_direct/trace.jsonl",
        "vsql_trace": "500_all_vsql/trace.jsonl",
        "why": "Loại view khỏi lúc chấm để điểm V-SQL phản ánh đúng SQL cuối trên bảng gốc.",
        "finding": "V-SQL giảm từ 33.6% xuống 31.6%. Stage 2 vẫn có ích ròng, nhưng Stage 1 sai nhiều.",
        "valid": True,
        "cost_usd": 0,
    },
    {
        "key": "32b_sample100",
        "title": "Model lớn hơn: 32B",
        "model": "Qwen2.5-Coder 32B",
        "view_mode": "manual",
        "schema_mode": "names",
        "source": "run",
        "metrics_dir": "32b_sample100",
        "why": "Kiểm tra xem model mã nguồn mở lớn hơn có đảo được kết quả không.",
        "finding": "Trên cùng 100 câu, so với 7B: Direct từ 42 lên 56, V-SQL chỉ từ 35 lên 37, nên khoảng cách rộng hơn.",
        "valid": True,
        "cost_usd": 0,
    },
    {
        "key": "luna_sample100",
        "title": "Model mới: Luna",
        "model": "GPT-6 Luna",
        "view_mode": "manual",
        "schema_mode": "names",
        "source": "run",
        "metrics_dir": "luna_sample100",
        "why": "GPT-3.5 và GPT-4 của paper đã ngừng hoạt động, nên thử model cloud rẻ còn dùng được.",
        "finding": "V-SQL tăng rõ nhưng vẫn thấp hơn Direct.",
        "valid": True,
        "cost_usd": 0.03,
    },
    {
        "key": "luna_sample100_described",
        "title": "Thêm mô tả cột vào schema",
        "model": "GPT-6 Luna",
        "view_mode": "manual",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "luna_sample100_described",
        "why": "Paper nói hiệu quả phụ thuộc vào cấu trúc và mô tả của view, nhưng không in định dạng prompt. Bản đầu chỉ có tên cột, nên thử thêm kiểu dữ liệu và mô tả cột.",
        "finding": "Stage 1 và V-SQL đều nhích lên, nhưng mẫu 100 câu chưa đủ để kết luận.",
        "valid": True,
        "cost_usd": 0.04,
    },
    {
        "key": "luna_500_described",
        "title": "Đủ 500 câu với Luna",
        "model": "GPT-6 Luna",
        "view_mode": "manual",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "luna_500_described",
        "why": "Thay mẫu nhỏ bằng toàn bộ tập dữ liệu để kết luận chắc chắn.",
        "finding": "V-SQL thua rõ. Phần lớn chênh lệch đến từ câu mà view thiếu bảng hoặc cột.",
        "valid": True,
        "cost_usd": 0.17,
    },
    {
        "key": "luna_500_fk",
        "title": "Mở rộng view theo khóa ngoại",
        "model": "GPT-6 Luna",
        "view_mode": "fk",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "luna_500_fk",
        "why": "Kiểm tra giả thuyết view thiếu dữ liệu là nguyên nhân chính: thêm mọi bảng và cột mà không đọc đáp án.",
        "finding": "V-SQL tăng từ 52.6% lên 59.4%. Chênh lệch với Direct còn 2 điểm và không có ý nghĩa thống kê (29 và 19 câu, p = 0.19).",
        "valid": True,
        "tag": "Mở rộng của nhóm",
    },
    {
        "key": "luna_500_gold",
        "title": "Mở rộng view theo gold SQL",
        "model": "GPT-6 Luna",
        "view_mode": "gold",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "luna_500_gold",
        "why": "Paper thiết kế view từ các join trong gold SQL. Bước này đi xa hơn: thêm đúng các cột và tổ hợp join mà đáp án cần.",
        "finding": "V-SQL đạt 59.6%, gần bằng view khóa ngoại dù đã đọc đáp án. Thêm view không còn giúp nhiều, và Stage 1 còn giảm khi model chọn view INNER JOIN làm mất dòng.",
        "valid": True,
        "tag": "Đối chứng",
    },
    {
        "key": "luna_500_paper",
        "title": "Gold chọn lọc theo bài báo",
        "model": "GPT-6 Luna",
        "view_mode": "paper",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "luna_500_paper",
        "why": "Paper dựa vào join hay dùng trong gold SQL và cảnh báo không nên tạo view cho mọi join. Bước này chỉ thêm tổ hợp bảng dùng từ 3 câu trở lên và dùng LEFT JOIN như view paper in ra.",
        "finding": "V-SQL đạt 58.6%, cao hơn rõ so với view thủ công (54 và 24 câu, p < 0.001). Direct vẫn cao hơn 2.8 điểm nhưng chưa đủ để kết luận (42 và 28 câu, p = 0.12). Bộ này cho điểm gần bằng view khóa ngoại và bộ 90 view, với prompt Stage 1 ngắn hơn khoảng 40%.",
        "valid": True,
        "tag": "Cấu hình chính",
    },
    {
        "key": "qwen3_4b_500_paper",
        "title": "Cấu hình chính với Qwen3 4B",
        "model": "Qwen3 4B",
        "view_mode": "paper",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "qwen3_4b_500_paper",
        "why": "Chạy cùng cấu hình trên model nhỏ nhất để xem kết quả có phụ thuộc vào Luna không.",
        "finding": "V-SQL đạt 42.2%, thấp hơn rõ so với Direct 47.4% (66 và 40 câu, p = 0.015). Stage 2 sửa đúng 47 câu Stage 1 sai, nhưng làm sai 19 câu Stage 1 đúng.",
        "valid": True,
        "tag": "Cấu hình chính",
    },
    {
        "key": "qwen7b_500_paper",
        "title": "Cấu hình chính với Qwen2.5-Coder 7B",
        "model": "Qwen2.5-Coder 7B",
        "view_mode": "paper",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "qwen7b_500_paper",
        "why": "Chạy lại model ban đầu với cấu hình chính, để so với lần đầu dùng view thủ công và schema chỉ tên cột.",
        "finding": "V-SQL đạt 38.6%, thấp hơn rõ so với Direct 49.8% (92 và 36 câu, p < 0.001). So với lần đầu, V-SQL tăng từ 31.6% (70 và 35 câu, p < 0.001), còn Direct từ 47.4% chưa đủ để kết luận (p = 0.18). Stage 2 làm sai 44 câu Stage 1 đúng, nhiều nhất trong 4 model. Ngoài ra, SQL cuối còn sót tên view ở 5 câu.",
        "valid": True,
        "tag": "Cấu hình chính",
    },
    {
        "key": "qwen32b_500_paper",
        "title": "Cấu hình chính với Qwen2.5-Coder 32B",
        "model": "Qwen2.5-Coder 32B",
        "view_mode": "paper",
        "schema_mode": "described",
        "source": "run",
        "metrics_dir": "qwen32b_500_paper",
        "why": "Chạy đủ 500 câu trên model cục bộ lớn nhất với cùng cấu hình.",
        "finding": "V-SQL đạt 54.2%, Direct đạt 56.2%, chênh lệch chưa đủ để kết luận (47 và 37 câu, p = 0.33). Trên cùng 100 câu của lần thử trước, V-SQL tăng từ 37 lên 48 câu (15 và 4 câu, p = 0.02), còn Direct từ 56 xuống 53 câu, chưa đủ để kết luận (p = 0.38).",
        "valid": True,
        "tag": "Cấu hình chính",
    },
]

def _load_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ex(item: dict | None) -> dict | None:
    return {"correct": item["correct"], "n": item["n"], "ex": item["ex"]} if item else None


def _from_stored(entry: dict) -> dict:
    direct = _load_json(os.path.join(config.OUTPUTS_DIR, "500_all_direct", "metrics.json")) or {}
    vsql = _load_json(os.path.join(config.OUTPUTS_DIR, "500_all_vsql", "metrics.json")) or {}

    def total(metrics):
        ex = metrics.get("EX", {}).get("total", 0)
        return {"correct": round(ex * entry["n"] / 100), "n": entry["n"], "ex": ex}

    return {
        "complete": bool(direct and vsql),
        "direct": total(direct),
        "stage1": None,
        "vsql": total(vsql),
        "pairs": None,
        "by_difficulty": {
            level: {
                "direct": {"ex": direct.get("EX", {}).get(level)},
                "stage1": None,
                "vsql": {"ex": vsql.get("EX", {}).get(level)},
            }
            for level in ("simple", "moderate", "challenging")
        },
        "by_db": None,
    }


def _from_rescored(metrics: dict) -> dict:
    keys = {"direct": "direct_ok", "stage1": "stage1_ok", "vsql": "vsql_ok"}
    pair = metrics["direct_vs_vsql"]
    return {
        "complete": True,
        "direct": _ex(metrics["total"]["direct_ok"]),
        "stage1": _ex(metrics["total"]["stage1_ok"]),
        "vsql": _ex(metrics["total"]["vsql_ok"]),
        "pairs": {"direct_only": pair["direct_only"], "vsql_only": pair["vsql_only"], "p": pair["mcnemar_exact_p"]},
        "by_difficulty": {level: {k: _ex(row[old]) for k, old in keys.items()} for level, row in metrics["by_difficulty"].items()},
        "by_db": {
            db: {"n": row["n"], "direct": row["direct_ok"], "stage1": row["stage1_ok"], "vsql": row["vsql_ok"]}
            for db, row in metrics["by_db"].items()
        },
    }


def _from_benchmark(metrics: dict) -> dict:
    pair = metrics["direct_vs_vsql_this_model"]
    return {
        "complete": not metrics.get("aborted"),
        "direct": _ex(metrics["this_model"]["direct"]),
        "stage1": _ex(metrics["this_model"]["stage1"]),
        "vsql": _ex(metrics["this_model"]["vsql"]),
        "pairs": {"direct_only": pair["a_only"], "vsql_only": pair["b_only"], "p": pair["exact_p"]},
        "by_difficulty": {level: {k: _ex(row[k]) for k in ("direct", "stage1", "vsql")} for level, row in metrics["by_difficulty"].items()},
        "by_db": metrics["by_db"],
        "view_leak": metrics.get("view_leak"),
        "classes": metrics.get("classes"),
        "view_gap": metrics.get("view_gap"),
        "stage_transitions": metrics.get("stage_transitions"),
        "new_spend": metrics.get("new_spend"),
    }


def _trace_paths(entry: dict) -> tuple[str | None, str | None]:
    if entry["source"] != "run":
        return None, None
    if "direct_trace" in entry:
        return os.path.join(config.OUTPUTS_DIR, entry["direct_trace"]), os.path.join(config.OUTPUTS_DIR, entry["vsql_trace"])
    base = os.path.join(config.OUTPUTS_DIR, entry["metrics_dir"])
    return os.path.join(base, "direct", "trace.jsonl"), os.path.join(base, "vsql", "trace.jsonl")


def list_runs() -> list[dict]:
    runs = []
    for step, entry in enumerate(CATALOG, start=1):
        row = {k: v for k, v in entry.items() if k not in ("direct_trace", "vsql_trace", "metrics_dir")}
        row["step"] = step
        metrics = _from_stored(entry) if entry["source"] == "stored_metrics" else None
        if entry["source"] == "run":
            raw = _load_json(os.path.join(config.OUTPUTS_DIR, entry["metrics_dir"], "metrics.json"))
            if raw:
                metrics = _from_rescored(raw) if "direct_vs_vsql" in raw else _from_benchmark(raw)
        row["available"] = metrics is not None
        if metrics:
            row.update(metrics)
            row.setdefault("n", metrics["direct"]["n"])
            spend = metrics.get("new_spend")
            if spend and "cost_usd" not in row:
                row["cost_usd"] = spend["usd"]
        direct, vsql = _trace_paths(entry)
        row["replayable"] = bool(metrics and direct and os.path.exists(direct) and vsql and os.path.exists(vsql))
        runs.append(row)
    return runs


def paper_table_rows() -> list[dict]:
    """This project's full 500-question runs, in the shape of the paper's results table."""
    rows = []
    view_names = {"manual": "view thủ công", "fk": "view khóa ngoại", "gold": "view gold SQL", "paper": "gold chọn lọc theo bài báo"}
    seen_direct = set()
    schema_names = {"names": "chỉ tên cột", "described": "có mô tả"}
    for run in list_runs():
        if not (run["available"] and run["valid"] and run.get("n") == 500 and run["source"] == "run"):
            continue
        local = run["model"].startswith("Qwen")
        source = "Ours (Local)" if local else "Ours (Cloud)"

        def row(method, series):
            levels = run["by_difficulty"]
            return {
                "source": source,
                "model": run["model"],
                "method": method,
                "sim": levels["simple"][series]["ex"],
                "mod": levels["moderate"][series]["ex"],
                "chall": levels["challenging"][series]["ex"],
                "total": run[series]["ex"],
            }

        direct_key = (run["model"], run["schema_mode"])
        if direct_key not in seen_direct:
            seen_direct.add(direct_key)
            rows.append(row(f"DIRECT ({schema_names[run['schema_mode']]})", "direct"))
        rows.append(row(f"V-SQL ({view_names[run['view_mode']]})", "vsql"))
    return rows


def load_traces(key: str) -> dict:
    """Returns {"direct": {qid: record}, "vsql": {qid: record}} for a replayable run."""
    entry = next((e for e in CATALOG if e["key"] == key), None)
    if not entry:
        raise ValueError(f"Không có lần chạy {key}")
    paths = dict(zip(("direct", "vsql"), _trace_paths(entry)))
    traces = {}
    for framework, path in paths.items():
        records = {}
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        records[record["question_id"]] = record
        traces[framework] = records
    return traces


def _reduction(gold_joins: float, dummy_joins: float) -> float:
    return (gold_joins - dummy_joins) / gold_joins * 100 if gold_joins else 0


def _em_flags(predicted: str, gold: str) -> dict:
    if not predicted or not gold:
        return {"strict": 0, "norm": 0}
    strict = int(normalize_strict(predicted) == normalize_strict(gold))
    try:
        return {"strict": strict, "norm": int(canonical_sql(predicted) == canonical_sql(gold))}
    except Exception:
        return {"strict": strict, "norm": strict}


def _percent(flags: list[int]) -> float:
    return sum(flags) / len(flags) * 100 if flags else 0


@functools.lru_cache(maxsize=16)
def _mechanism_cached(key: str, stamp: float) -> dict:
    traces = load_traces(key)
    direct, vsql = traces["direct"], traces["vsql"]
    ids = [qid for qid in vsql if qid in direct]
    em = {qid: {"direct": _em_flags(direct[qid]["final_sql"], vsql[qid]["gold_sql"]), "vsql": _em_flags(vsql[qid]["final_sql"], vsql[qid]["gold_sql"])} for qid in ids}

    def mean(values):
        return sum(values) / len(values) if values else 0

    def measure(group):
        stage1 = [vsql[qid]["trace"]["stage1"] for qid in group]
        stage2 = [vsql[qid]["trace"]["stage2"] for qid in group]
        gold_joins = mean([vsql[qid]["gold_joins"] for qid in group])
        dummy_joins = mean([s["joins"] for s in stage1])
        tokens_dummy = mean([s["tokens"] for s in stage1])
        tokens_final = mean([s["tokens"] for s in stage2])
        return {
            "count": len(group),
            "gold_joins": gold_joins,
            "dummy_joins": dummy_joins,
            "final_joins": mean([s["joins"] for s in stage2]),
            "reduction_pct": _reduction(gold_joins, dummy_joins),
            "view_leaks": sum(bool(s.get("view_leak")) for s in stage2),
            "tokens_dummy": tokens_dummy,
            "tokens_final": tokens_final,
            "d_tokens": mean([direct[qid]["trace"]["tokens"] for qid in group]),
            "v_tokens": tokens_dummy + tokens_final,
        }

    groups = [(label, [qid for qid in ids if vsql[qid]["difficulty"] == level]) for level, label in LEVELS]
    em_rows = {}
    for framework in ("direct", "vsql"):
        row = {}
        for level, label in LEVELS:
            group = [qid for qid in ids if vsql[qid]["difficulty"] == level]
            row[level] = {kind: _percent([em[qid][framework][kind] for qid in group]) for kind in ("strict", "norm")}
        row["total"] = {kind: _percent([em[qid][framework][kind] for qid in ids]) for kind in ("strict", "norm")}
        em_rows[framework] = row
    return {
        "by_difficulty": [{"difficulty": label, **measure(group)} for label, group in groups] + [{"difficulty": "TOTAL", **measure(ids)}],
        "by_db": sorted(
            ({"db_id": db, **measure([qid for qid in ids if vsql[qid]["db_id"] == db])} for db in {vsql[qid]["db_id"] for qid in ids}),
            key=lambda row: -row["count"],
        ),
        "em": em_rows,
        "em_by_question": em,
        "latency": {
            "direct": mean([direct[qid]["trace"]["latency_s"] for qid in ids]),
            "vsql": mean([vsql[qid]["trace"]["stage1"]["latency_s"] + vsql[qid]["trace"]["stage2"]["latency_s"] for qid in ids]),
        },
    }


def run_mechanism(key: str) -> dict | None:
    """JOIN, token, exact match and latency measures of a run, computed from its traces. None without traces."""
    entry = next((e for e in CATALOG if e["key"] == key), None)
    if not entry:
        raise ValueError(f"Không có lần chạy {key}")
    paths = [path for path in _trace_paths(entry) if path]
    if len(paths) != 2 or not all(os.path.exists(path) for path in paths):
        return None
    return _mechanism_cached(key, max(os.path.getmtime(path) for path in paths))


def run_config(key: str) -> dict:
    entry = next((e for e in CATALOG if e["key"] == key), None)
    if not entry:
        raise ValueError(f"Không có lần chạy {key}")
    return {"model": entry["model"], "view_mode": entry["view_mode"], "schema_mode": entry["schema_mode"]}
