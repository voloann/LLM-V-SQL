"""Compares the manual, paper, fk and gold view sets question by question and writes outputs/view_extension_analysis.json.

Questions are grouped by what the manual views lack for them (table, column, join, or nothing), so the same 500
questions can be followed across all view sets. Grouping reads gold SQL and is done after the fact, so it
explains differences rather than testing a prediction made in advance.

Usage: python scripts/analyze_view_extension.py
"""
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config
from build_views import gold_gaps, load_db_schema, load_manual_views

RUNS = {"manual": "luna_500_described", "paper": "luna_500_paper", "fk": "luna_500_fk", "gold": "luna_500_gold"}
GROUP_LABELS = {
    "table": "View thủ công thiếu bảng",
    "column": "View thủ công thiếu cột",
    "join": "View thủ công đủ bảng và cột, thiếu tổ hợp join",
    "none": "View thủ công đủ tất cả",
}


def gap_group(gaps: list[str]) -> str:
    kinds = {gap.split(":", 1)[0] for gap in gaps}
    for kind in ("table", "column", "join"):
        if kind in kinds:
            return kind
    return "none"


def mcnemar(a: list[bool], b: list[bool]) -> dict:
    a_only = sum(x and not y for x, y in zip(a, b))
    b_only = sum(y and not x for x, y in zip(a, b))
    n = a_only + b_only
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1)) / 2**n) if n else 1.0
    return {"a_only": a_only, "b_only": b_only, "p": p}


def _load(run_dir: str) -> dict | None:
    path = os.path.join(config.OUTPUTS_DIR, run_dir, "per_question.jsonl")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rows = {r["question_id"]: r for r in map(json.loads, f) if "vsql_ok" in r and "direct_ok" in r}
    return rows or None


def _ex(values: list[bool]) -> dict:
    return {"correct": sum(values), "n": len(values), "ex": round(sum(values) / len(values) * 100, 2) if values else 0.0}


def _trace_totals(run_dir: str) -> dict:
    totals = collections.Counter()
    latency = []
    path = os.path.join(config.OUTPUTS_DIR, run_dir, "vsql", "trace.jsonl")
    with open(path, encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)["trace"]
            totals["stage1_prompt_tokens"] += trace["stage1"]["prompt_tokens"]
            totals["stage2_prompt_tokens"] += trace["stage2"]["prompt_tokens"]
            totals["completion_tokens"] += trace["stage1"]["tokens"] + trace["stage2"]["tokens"]
            totals["stage1_joins"] += trace["stage1"]["joins"]
            totals["final_joins"] += trace["stage2"]["joins"]
            totals["calls_failed"] += bool(trace["stage1"].get("error") or trace["stage2"].get("error"))
            latency.append(trace["stage1"]["latency_s"] + trace["stage2"]["latency_s"])
    latency.sort()
    totals = dict(totals)
    totals["median_latency_s"] = latency[len(latency) // 2] if latency else 0
    return totals


def main():
    with open(config.DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    runs = {mode: _load(run_dir) for mode, run_dir in RUNS.items()}
    runs = {mode: rows for mode, rows in runs.items() if rows}
    if "manual" not in runs:
        raise SystemExit("Thiếu kết quả của lần chạy view thủ công")
    modes = list(runs)
    common = [q for q in questions if all(q["question_id"] in runs[m] for m in modes)]

    schemas, manual_views = {}, {}
    groups = collections.defaultdict(list)
    for q in common:
        db = q["db_id"]
        schemas.setdefault(db, load_db_schema(db))
        manual_views.setdefault(db, load_manual_views(db))
        groups[gap_group(gold_gaps(q["SQL"], manual_views[db], schemas[db]))].append(q["question_id"])

    def result(ids, mode, key):
        return [runs[mode][qid][key] for qid in ids]

    ids_all = [q["question_id"] for q in common]
    direct = result(ids_all, "manual", "direct_ok")
    analysis = {
        "questions": len(common),
        "modes": modes,
        "direct": _ex(direct),
        "by_mode": {},
        "pairs": {},
        "groups": [],
        "by_difficulty": {},
    }
    for mode in modes:
        rows = [runs[mode][qid] for qid in ids_all]
        vsql = [r["vsql_ok"] for r in rows]
        stage1 = [r["stage1_ok"] for r in rows]
        transitions = collections.Counter(("S1ok" if r["stage1_ok"] else "S1bad") + "->" + ("FINok" if r["vsql_ok"] else "FINbad") for r in rows)
        analysis["by_mode"][mode] = {
            "stage1": _ex(stage1),
            "vsql": _ex(vsql),
            "view_leak": sum(r.get("view_leak", False) for r in rows),
            "stage1_classes": dict(collections.Counter(r["stage1_class"] for r in rows).most_common()),
            "vsql_classes": dict(collections.Counter(r["vsql_class"] for r in rows).most_common()),
            "transitions": dict(transitions),
            "direct_only_breakdown": {
                "stage1_wrong": sum(r["direct_ok"] and not r["vsql_ok"] and not r["stage1_ok"] for r in rows),
                "stage2_broke": sum(r["direct_ok"] and not r["vsql_ok"] and r["stage1_ok"] for r in rows),
            },
            "traces": _trace_totals(RUNS[mode]),
        }
        analysis["pairs"][f"direct_vs_{mode}"] = mcnemar(direct, vsql)
        if mode != "manual":
            analysis["pairs"][f"manual_vs_{mode}"] = mcnemar(result(ids_all, "manual", "vsql_ok"), vsql)
    for left, right in (("fk", "gold"), ("paper", "fk"), ("paper", "gold")):
        if {left, right} <= set(modes):
            analysis["pairs"][f"{left}_vs_{right}"] = mcnemar(result(ids_all, left, "vsql_ok"), result(ids_all, right, "vsql_ok"))

    for group in ("table", "column", "join", "none"):
        ids = groups.get(group, [])
        row = {"group": group, "label": GROUP_LABELS[group], "n": len(ids), "direct": _ex(result(ids, "manual", "direct_ok")), "vsql": {}, "stage1": {}, "pairs": {}}
        for mode in modes:
            row["vsql"][mode] = _ex(result(ids, mode, "vsql_ok"))
            row["stage1"][mode] = _ex(result(ids, mode, "stage1_ok"))
            row["pairs"][mode] = mcnemar(result(ids, "manual", "direct_ok"), result(ids, mode, "vsql_ok"))
        analysis["groups"].append(row)

    for level in ("simple", "moderate", "challenging"):
        ids = [q["question_id"] for q in common if q["difficulty"] == level]
        analysis["by_difficulty"][level] = {"n": len(ids), "direct": _ex(result(ids, "manual", "direct_ok")), "vsql": {m: _ex(result(ids, m, "vsql_ok")) for m in modes}}

    out_path = os.path.join(config.OUTPUTS_DIR, "view_extension_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(json.dumps(analysis, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
