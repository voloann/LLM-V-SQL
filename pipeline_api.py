"""HTTP API for the step-by-step pipeline demo and the catalog of experiment runs."""
import collections
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
import experiment_runs
import model_registry
from pipeline_demo import DEFAULT_BUDGET_USD, MAX_BUDGET_USD, VIEW_LABELS, RunBusy, RunManager, RunRequest, estimate, load_questions

router = APIRouter(prefix="/api")
manager = RunManager(save_runs=True)
QUESTIONS = load_questions()

VIEW_DESCRIPTIONS = {
    "manual": "27 view viết tay từ các phép join trong gold SQL, chỉ gồm một phần số cột.",
    "paper": "View thủ công có thêm các cột gold SQL cần, cộng view LEFT JOIN cho tổ hợp bảng dùng từ 3 câu trở lên. Bám cách paper mô tả và vẫn đọc gold SQL.",
    "fk": "View thủ công có thêm mọi cột, và thêm view cho từng bảng còn thiếu theo khóa ngoại. Phần mở rộng không đọc gold SQL.",
    "gold": "View thủ công có thêm đúng các cột và mọi tổ hợp join mà gold SQL cần, cách paper cảnh báo là chưa chắc tốt nhất.",
}


class PipelineRunBody(BaseModel):
    selection: dict
    frameworks: list[str]
    source: str = "live"
    model: Optional[str] = None
    view_mode: str = "manual"
    schema_mode: str = "described"
    replay_run: Optional[str] = None
    budget_usd: float = DEFAULT_BUDGET_USD
    step_delay_s: float = 0.0


def _request(body: PipelineRunBody) -> RunRequest:
    return RunRequest(**body.model_dump())


def _coverage() -> dict:
    path = os.path.join(config.VIEWS_DIR, "coverage_report.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("totals", {})


@router.get("/runs")
def get_runs():
    analysis_path = os.path.join(config.OUTPUTS_DIR, "view_extension_analysis.json")
    analysis = None
    if os.path.exists(analysis_path):
        with open(analysis_path, encoding="utf-8") as f:
            analysis = json.load(f)
    runs = experiment_runs.list_runs()
    mechanism = {}
    for run in runs:
        if run["key"] in experiment_runs.MAIN_RUNS and run["available"]:
            mechanism[run["key"]] = {k: v for k, v in experiment_runs.run_mechanism(run["key"]).items() if k != "em_by_question"}
    return {"runs": runs, "main_runs": list(experiment_runs.MAIN_RUNS), "mechanism": mechanism, "coverage": _coverage(), "analysis": analysis}


@router.get("/pipeline/options")
def get_options():
    coverage = _coverage()
    counts = collections.Counter(q["db_id"] for q in QUESTIONS)
    difficulties = collections.Counter(q["difficulty"] for q in QUESTIONS)
    return {
        "models": model_registry.list_models(),
        "frameworks": [
            {"id": "direct", "label": "Direct", "description": "Một lần gọi model, sinh SQL thẳng trên bảng gốc."},
            {"id": "vsql", "label": "V-SQL", "description": "Stage 1 viết Dummy SQL trên view, Stage 2 tái dựng SQL trên bảng gốc."},
        ],
        "view_modes": [
            {"id": mode, "label": label, "description": VIEW_DESCRIPTIONS[mode], "stats": coverage.get(mode)}
            for mode, label in VIEW_LABELS.items()
        ],
        "schema_modes": [
            {"id": "described", "label": "Có kiểu và mô tả cột", "description": "Kiểu lấy từ database, mô tả lấy từ database_description của BIRD."},
            {"id": "names", "label": "Chỉ tên cột", "description": "Bản đầu tiên của project."},
        ],
        "databases": [{"db_id": db, "count": counts[db]} for db in sorted(counts)],
        "difficulties": [{"id": level, "count": difficulties[level]} for level in ("simple", "moderate", "challenging")],
        "parameters": {"temperature": config.TEMPERATURE, "top_p": config.TOP_P, "max_tokens": config.MAX_TOKENS},
        "budget": {"default": DEFAULT_BUDGET_USD, "max": MAX_BUDGET_USD},
        "total_questions": len(QUESTIONS),
    }


@router.get("/pipeline/questions")
def get_pipeline_questions(db: Optional[str] = None, difficulty: Optional[str] = None, search: Optional[str] = None, limit: int = 500):
    search_text = (search or "").lower()
    items = [
        {k: q.get(k) for k in ("question_id", "db_id", "difficulty", "question", "evidence")}
        for q in QUESTIONS
        if (not db or db == "all" or q["db_id"] == db)
        and (not difficulty or difficulty == "all" or q["difficulty"] == difficulty)
        and (not search_text or search_text in q["question"].lower())
    ]
    return {"total": len(items), "questions": items[:limit]}


@router.post("/pipeline/estimate")
def post_estimate(body: PipelineRunBody):
    if body.source != "live" or not body.model:
        return {"questions": 0, "llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "seconds": 0.0}
    if body.model not in model_registry.MODELS or body.view_mode not in VIEW_LABELS:
        raise HTTPException(status_code=400, detail="Cấu hình không hợp lệ")
    return estimate(_request(body), QUESTIONS)


@router.post("/pipeline/runs")
def post_run(body: PipelineRunBody):
    try:
        run = manager.start(_request(body))
    except RunBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run_id": run.id, "total_questions": len(run.questions), "light_events": run.light_events, "frameworks": run.frameworks}


def _get_run(run_id: str):
    run = manager.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy")
    return run


@router.get("/pipeline/runs/{run_id}")
def get_run(run_id: str):
    return _get_run(run_id).snapshot()


@router.get("/pipeline/runs/{run_id}/questions/{question_id}")
def get_question_detail(run_id: str, question_id: int):
    run = _get_run(run_id)
    detail = {
        framework: list(run.details[(question_id, framework)].values())
        for framework in run.frameworks
        if (question_id, framework) in run.details
    }
    return {"question_id": question_id, "steps": detail, "results": run.results.get(question_id, {})}


@router.post("/pipeline/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    _get_run(run_id)
    manager.cancel(run_id)
    return {"ok": True}


def _stream(run, start: int):
    index = start
    while True:
        with run.condition:
            if index >= len(run.events):
                run.condition.wait(timeout=15)
            batch = run.events[index:]
        if not batch:
            yield ": ping\n\n"
            continue
        for event in batch:
            index += 1
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            if event["type"] == "run_done":
                return


@router.get("/pipeline/runs/{run_id}/events")
def stream_events(run_id: str, start: int = 0):
    run = _get_run(run_id)
    return StreamingResponse(_stream(run, start), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
