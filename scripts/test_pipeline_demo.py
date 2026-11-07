"""Tests for the step-by-step pipeline demo backend. Run: python scripts/test_pipeline_demo.py"""
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config
import experiment_runs
import pipeline_demo
from pipeline_demo import RunManager, RunRequest, select_questions
from sql_eval import EvalContext, execute_query

with open(config.DATA_PATH, encoding="utf-8") as f:
    QUESTIONS = json.load(f)
BY_ID = {q["question_id"]: q for q in QUESTIONS}
TOXICOLOGY = [q for q in QUESTIONS if q["db_id"] == "toxicology"]


def stats(prompt_tokens=100, completion_tokens=20, error=None):
    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens, "latency_s": 0.01, "raw_content": "```sql\nraw\n```", "error": error}


def gold_answering_llm(question):
    """Stage 1 writes a bad dummy query, the final call returns the gold SQL."""
    calls = []

    def llm(prompt):
        calls.append(prompt)
        if "# view query" in prompt or "# db schema" in prompt:
            return question["SQL"], stats()
        return "SELECT no_such_column FROM v_atom_molecule", stats()

    return llm


def run_to_end(manager, request, timeout=120):
    run = manager.start(request)
    deadline = time.time() + timeout
    while run.status in ("queued", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert run.status not in ("queued", "running"), run.status
    return run


def test_select_one_id():
    picked = select_questions(QUESTIONS, {"mode": "ids", "ids": [TOXICOLOGY[0]["question_id"]]})
    assert [q["question_id"] for q in picked] == [TOXICOLOGY[0]["question_id"]]


def test_select_filter_with_limit_is_reproducible_with_seed():
    selection = {"mode": "filter", "db": "toxicology", "difficulty": "simple", "limit": 3, "seed": 7}
    first, second = select_questions(QUESTIONS, selection), select_questions(QUESTIONS, selection)
    assert len(first) == 3 and [q["question_id"] for q in first] == [q["question_id"] for q in second]
    assert all(q["db_id"] == "toxicology" and q["difficulty"] == "simple" for q in first)


def test_select_all_returns_500():
    assert len(select_questions(QUESTIONS, {"mode": "all"})) == 500


def test_prediction_cannot_change_database():
    ctx = EvalContext()
    result = execute_query(ctx.physical("toxicology"), "DROP TABLE atom")
    assert result.error, "write must fail on a read-only connection"
    count = ctx.physical("toxicology").execute("SELECT COUNT(*) FROM atom").fetchone()[0]
    assert count > 0


def test_score_compares_rows_as_sets_and_counts_differences():
    ctx = EvalContext()
    q = TOXICOLOGY[0]
    good = ctx.score(q, q["SQL"])
    assert good["ok"] and good["class"] == "correct", good
    bad = ctx.score(q, "SELECT 'not the answer', 'x', 'y', 'z'")
    assert not bad["ok"] and bad["class"] in ("wrong_values", "wrong_column_count"), bad
    assert bad["only_pred"] == 1


def test_vsql_steps_show_input_and_output_for_each_stage():
    q = TOXICOLOGY[0]
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: gold_answering_llm(question)), RunRequest(selection={"mode": "ids", "ids": [q["question_id"]]}, frameworks=["vsql"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    assert run.status == "done", (run.status, run.message)
    steps = run.details[(q["question_id"], "vsql")]
    assert list(steps) == ["input", "mapping", "stage1", "stage1_exec", "linking", "stage2", "execute", "score"], list(steps)
    for step in steps.values():
        assert step["status"] in ("done", "error"), step
        assert step["inputs"] and step["outputs"], step["id"]
    assert steps["stage1_exec"]["status"] == "error"
    assert steps["score"]["outputs"][0]["value"]["ok"] is True
    result = run.results[q["question_id"]]["vsql"]
    assert result["ok"] and not result["stage1_ok"], result


def test_direct_steps_and_events_arrive_running_then_done():
    q = TOXICOLOGY[1]
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: gold_answering_llm(question)), RunRequest(selection={"mode": "ids", "ids": [q["question_id"]]}, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    assert list(run.details[(q["question_id"], "direct")]) == ["input", "mapping", "direct", "execute", "score"]
    states = [(e["step"]["id"], e["step"]["status"]) for e in run.events if e["type"] == "step"]
    assert states.index(("direct", "running")) < states.index(("direct", "done"))
    assert run.events[0]["type"] == "run_start" and run.events[-1]["type"] == "run_done"


def test_big_runs_send_light_events_but_keep_details():
    selection = {"mode": "filter", "db": "toxicology", "limit": pipeline_demo.FULL_EVENT_LIMIT + 1, "seed": 1}
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: (lambda prompt: (question["SQL"], stats()))), RunRequest(selection=selection, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    steps = [e["step"] for e in run.events if e["type"] == "step"]
    assert steps and all("inputs" not in s for s in steps)
    assert all(run.details[key]["score"]["inputs"] for key in run.details)
    assert run.summary["frameworks"]["direct"]["correct"] == pipeline_demo.FULL_EVENT_LIMIT + 1


def test_summary_counts_cost_and_pairs_frameworks():
    q = TOXICOLOGY[2]
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: gold_answering_llm(question)), RunRequest(selection={"mode": "ids", "ids": [q["question_id"]]}, frameworks=["direct", "vsql"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    assert run.summary["frameworks"]["direct"]["ex"] == 100.0
    assert run.summary["frameworks"]["vsql"]["stage1_correct"] == 0
    assert run.summary["pairs"]["both"] == 1
    expected = 3 * (100 * 0.10 + 20 * 0.50) / 1_000_000
    assert abs(run.summary["cost_usd"] - expected) < 1e-9, run.summary["cost_usd"]


def test_budget_stops_a_live_run():
    selection = {"mode": "filter", "db": "toxicology", "limit": 5, "seed": 1}
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: (lambda prompt: (question["SQL"], stats(1_000_000, 0)))), RunRequest(selection=selection, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live", budget_usd=0.15))
    assert run.status == "budget_stopped", run.status
    assert run.summary["frameworks"]["direct"]["done"] == 2


def test_repeated_llm_errors_abort_the_run():
    selection = {"mode": "filter", "db": "toxicology", "limit": 6, "seed": 1}
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: (lambda prompt: ("", stats(error="boom")))), RunRequest(selection=selection, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    assert run.status == "error" and "boom" in run.message, (run.status, run.message)
    assert run.summary["frameworks"]["direct"]["done"] == pipeline_demo.MAX_CONSECUTIVE_ERRORS


def test_cancel_stops_between_steps():
    selection = {"mode": "filter", "db": "toxicology", "limit": 20, "seed": 1}

    def slow_factory(request, question, framework):
        def llm(prompt):
            time.sleep(0.05)
            return question["SQL"], stats()
        return llm

    manager = RunManager(llm_factory=slow_factory)
    run = manager.start(RunRequest(selection=selection, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    time.sleep(0.12)
    manager.cancel(run.id)
    deadline = time.time() + 20
    while run.status == "running" and time.time() < deadline:
        time.sleep(0.02)
    assert run.status == "cancelled", run.status
    assert run.summary["frameworks"]["direct"]["done"] < 20


def test_only_one_live_run_at_a_time():
    selection = {"mode": "filter", "db": "toxicology", "limit": 10, "seed": 1}

    def slow_factory(request, question, framework):
        return lambda prompt: (time.sleep(0.05), (question["SQL"], stats()))[1]

    manager = RunManager(llm_factory=slow_factory)
    request = RunRequest(selection=selection, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live")
    run = manager.start(request)
    try:
        manager.start(request)
        raise AssertionError("second live run should be refused")
    except pipeline_demo.RunBusy:
        pass
    manager.cancel(run.id)


def test_replay_reproduces_stored_scores_without_calling_a_model():
    stored = {}
    with open("outputs/luna_500_described/per_question.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["db_id"] == "toxicology":
                stored[row["question_id"]] = row

    def forbidden(request, question, framework):
        raise AssertionError("replay must not call a model")

    run = run_to_end(RunManager(llm_factory=forbidden), RunRequest(selection={"mode": "ids", "ids": sorted(stored)}, frameworks=["direct", "vsql"], source="replay", replay_run="luna_500_described", step_delay_s=0), timeout=300)
    assert run.status == "done", (run.status, run.message)
    assert run.summary["cost_usd"] == 0
    for qid, row in stored.items():
        assert run.results[qid]["direct"]["ok"] == row["direct_ok"], qid
        assert run.results[qid]["vsql"]["ok"] == row["vsql_ok"], qid
        assert run.results[qid]["vsql"]["stage1_ok"] == row["stage1_ok"], qid


def test_replay_prompt_matches_the_stored_runs_configuration():
    q = TOXICOLOGY[0]
    run = run_to_end(RunManager(), RunRequest(selection={"mode": "ids", "ids": [q["question_id"]]}, frameworks=["vsql"], source="replay", replay_run="luna_500_described", step_delay_s=0))
    prompt = run.details[(q["question_id"], "vsql")]["stage1"]["inputs"][0]["value"]
    assert "-- " in prompt and "v_atom_molecule(" in prompt, prompt[:300]


def test_replay_skips_questions_the_stored_run_does_not_have():
    sample = json.load(open("outputs/32b_sample100/questions.json", encoding="utf-8"))
    have = {q["question_id"] for q in sample}
    missing = next(q["question_id"] for q in QUESTIONS if q["question_id"] not in have)
    try:
        RunManager().start(RunRequest(selection={"mode": "ids", "ids": [missing]}, frameworks=["direct"], source="replay", replay_run="32b_sample100"))
        raise AssertionError("expected a refusal")
    except ValueError:
        pass


def test_events_never_contain_the_api_key():
    q = TOXICOLOGY[0]
    run = run_to_end(RunManager(llm_factory=lambda request, question, framework: (lambda prompt: ("", stats(error="bad key [redacted]")))), RunRequest(selection={"mode": "ids", "ids": [q["question_id"]]}, frameworks=["direct"], model="gpt-6-luna", view_mode="manual", schema_mode="names", source="live"))
    key_path = os.path.expanduser("~/.config/llm-v-sql/llm.key")
    if os.path.exists(key_path):
        with open(key_path, encoding="utf-8") as f:
            key = f.read().strip()
        assert key not in json.dumps(run.events, default=str)


def test_run_catalog_reports_known_numbers():
    runs = {r["key"]: r for r in experiment_runs.list_runs()}
    assert runs["stored_7b"]["vsql"]["ex"] == 33.6
    assert runs["rescored_7b"]["direct"]["ex"] == 47.4 and runs["rescored_7b"]["stage1"]["ex"] == 26.4 and runs["rescored_7b"]["vsql"]["ex"] == 31.6
    assert runs["luna_500_described"]["direct"]["ex"] == 61.4 and runs["luna_500_described"]["vsql"]["ex"] == 52.6
    assert runs["luna_500_described"]["pairs"]["direct_only"] == 60 and runs["luna_500_described"]["pairs"]["vsql_only"] == 16
    assert runs["32b_sample100"]["n"] == 100
    assert runs["luna_500_described"]["by_difficulty"]["simple"]["vsql"]["ex"] == 62.84


def test_catalog_marks_replayable_runs():
    runs = {r["key"]: r for r in experiment_runs.list_runs()}
    assert runs["luna_500_described"]["replayable"] and runs["rescored_7b"]["replayable"]
    assert not runs["stored_7b"]["replayable"]


def test_estimate_scales_with_questions_and_is_free_for_local():
    one = pipeline_demo.estimate(RunRequest(selection={"mode": "filter", "db": "toxicology", "limit": 1, "seed": 1}, frameworks=["vsql"], model="gpt-6-luna", view_mode="fk", schema_mode="described", source="live"), QUESTIONS)
    many = pipeline_demo.estimate(RunRequest(selection={"mode": "all"}, frameworks=["direct", "vsql"], model="gpt-6-luna", view_mode="fk", schema_mode="described", source="live"), QUESTIONS)
    local = pipeline_demo.estimate(RunRequest(selection={"mode": "all"}, frameworks=["vsql"], model="qwen2.5-coder-32b-16k", view_mode="fk", schema_mode="described", source="live"), QUESTIONS)
    assert 0 < one["cost_usd"] < many["cost_usd"]
    assert many["questions"] == 500 and many["llm_calls"] == 1500
    assert local["cost_usd"] == 0 and local["seconds"] > 3600


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    failed = 0
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_") and only in name:
            try:
                test()
                print("PASS", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, repr(exc)[:600])
    print("failed:", failed)
    sys.exit(1 if failed else 0)
