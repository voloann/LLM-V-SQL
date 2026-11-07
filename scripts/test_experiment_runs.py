"""Tests for the run catalog and the measures computed from traces. Run: python scripts/test_experiment_runs.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import experiment_runs


def test_main_runs_are_in_the_catalog_with_the_main_configuration():
    entries = {e["key"]: e for e in experiment_runs.CATALOG}
    assert len(experiment_runs.MAIN_RUNS) == 4
    for key in experiment_runs.MAIN_RUNS:
        assert entries[key]["view_mode"] == "paper" and entries[key]["schema_mode"] == "described", key


def test_every_main_run_is_complete_and_has_a_finding():
    runs = {r["key"]: r for r in experiment_runs.list_runs()}
    for key in experiment_runs.MAIN_RUNS:
        run = runs[key]
        assert run["available"] and run["n"] == 500, key
        assert run.get("finding"), key
        assert f"{run['vsql']['ex']:.1f}%" in run["finding"], (key, run["vsql"]["ex"])


def test_mechanism_totals_match_the_stored_fk_trace():
    total = experiment_runs.run_mechanism("luna_500_fk")["by_difficulty"][-1]
    assert total["difficulty"] == "TOTAL" and total["count"] == 500
    assert total["view_leaks"] == 0
    assert abs(total["dummy_joins"] - 64 / 500) < 1e-9, total
    assert abs(total["final_joins"] - 481 / 500) < 1e-9, total


def test_mechanism_covers_every_database_once():
    rows = experiment_runs.run_mechanism("luna_500_fk")["by_db"]
    assert len(rows) == 11
    assert sum(row["count"] for row in rows) == 500


def test_mechanism_reports_latency_for_both_frameworks():
    latency = experiment_runs.run_mechanism("luna_500_fk")["latency"]
    assert 0 < latency["direct"] < latency["vsql"], latency


def test_reduction_handles_no_gold_joins_and_can_be_negative():
    assert experiment_runs._reduction(0, 0) == 0
    assert experiment_runs._reduction(2, 1) == 50
    assert experiment_runs._reduction(1, 2) == -100


def test_em_flags_separate_strict_from_normalized():
    assert experiment_runs._em_flags("select a  from t;", "SELECT a FROM t") == {"strict": 1, "norm": 1}
    assert experiment_runs._em_flags("SELECT T1.a FROM t AS T1", "SELECT a FROM t")["strict"] == 0
    assert experiment_runs._em_flags("", "SELECT a FROM t") == {"strict": 0, "norm": 0}
    assert experiment_runs._em_flags("not sql ((", "SELECT a FROM t") == {"strict": 0, "norm": 0}


def test_paper_table_keeps_one_direct_row_per_model_and_schema():
    level = {"direct": {"ex": 1}, "vsql": {"ex": 1}}
    levels = {"simple": level, "moderate": level, "challenging": level}

    def run(model, schema, view):
        return {
            "available": True, "valid": True, "n": 500, "source": "run", "model": model, "schema_mode": schema,
            "view_mode": view, "by_difficulty": levels, "direct": {"ex": 1}, "vsql": {"ex": 1},
        }

    original = experiment_runs.list_runs
    experiment_runs.list_runs = lambda: [run("Qwen 7B", "names", "manual"), run("Qwen 7B", "described", "paper"), run("Luna", "described", "manual"), run("Luna", "described", "fk")]
    try:
        rows = experiment_runs.paper_table_rows()
    finally:
        experiment_runs.list_runs = original
    direct = [r for r in rows if r["method"].startswith("DIRECT")]
    assert len(direct) == 3, direct
    assert len(rows) == 7, rows


if __name__ == "__main__":
    failed = 0
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_"):
            try:
                test()
                print("PASS", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, repr(exc)[:400])
    print("failed:", failed)
    sys.exit(1 if failed else 0)
