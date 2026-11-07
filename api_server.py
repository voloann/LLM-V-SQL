import os
import sys
import json
import sqlite3
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Thêm root vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from sql_utils import count_joins, format_view_schema_header
from v_sql_pipeline_LLM import run_v_sql_inference, run_direct_baseline_inference
from run_experiment import load_db_configs
from pipeline_api import router as pipeline_router
import experiment_runs
import llm_client

app = FastAPI(title="V-SQL Studio API", version="1.0.0")

# The pipeline API can spend the OpenAI budget, so only pages served from this machine may call it.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router)

# Nạp dữ liệu nền
DB_CONFIGS = load_db_configs(view_mode="paper", schema_mode="described")

ALL_QUESTIONS = []
if os.path.exists(config.DATA_PATH):
    with open(config.DATA_PATH, "r", encoding="utf-8") as f:
        ALL_QUESTIONS = json.load(f)

PAPER_RESULTS = {
    "GPT-3.5-turbo": {"TA-SQL": 43.80, "V-SQL": 45.40, "SIM": 58.11, "MOD": 43.60, "CHALL": 31.37},
    "GPT-4-turbo": {"V-SQL": 52.80, "SIM": 62.16, "MOD": 51.60, "CHALL": 40.19},
    "GPT-4": {"V-SQL": 56.00, "SIM": 62.84, "MOD": 59.60, "CHALL": 37.25}
}

class InferRequest(BaseModel):
    db_id: str
    question: str
    evidence: Optional[str] = ""
    method: str = "vsql"  # "vsql" or "direct"

def execute_sqlite_query(db_id: str, sql: str, limit: int = 50):
    db_file = os.path.join(config.DB_ROOT, db_id, f"{db_id}.sqlite")
    if not os.path.exists(db_file):
        return {"columns": [], "rows": [], "error": f"Database {db_id} not found."}
    try:
        conn = sqlite3.connect(db_file, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(limit)
        conn.close()
        return {"columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"columns": [], "rows": [], "error": str(e)}

@app.get("/api/health")
def get_health():
    lm_ok = False
    model_name = getattr(config, "SELECTED_MODEL", "qwen2.5-coder-7b-instruct")
    base_url = getattr(config, "LLM_BASE_URL", "http://localhost:1234/v1")
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url}/models")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                if "data" in data and len(data["data"]) > 0:
                    model_name = data["data"][0].get("id", model_name)
                lm_ok = True
    except Exception:
        lm_ok = False

    return {
        "status": "online",
        "lm_studio": {
            "connected": lm_ok,
            "url": base_url,
            "model": model_name
        },
        "databases_count": len(DB_CONFIGS),
        "total_questions": len(ALL_QUESTIONS)
    }

@app.get("/api/databases")
def get_databases():
    result = []
    
    # JOIN của cấu hình chính, đo từ trace thật của Luna
    mechanism = experiment_runs.run_mechanism("luna_500_paper")
    reduction_map = {row["db_id"]: row for row in mechanism["by_db"]} if mechanism else {}

    # Gom các câu hỏi mẫu theo DB
    db_samples = {}
    for q in ALL_QUESTIONS:
        d = q.get("db_id")
        if d not in db_samples:
            db_samples[d] = []
        if len(db_samples[d]) < 6:
            db_samples[d].append({
                "question_id": q.get("question_id"),
                "question": q.get("question"),
                "evidence": q.get("evidence", ""),
                "difficulty": q.get("difficulty", "simple")
            })

    for db_id, cfg in DB_CONFIGS.items():
        views = cfg.get("parsed_views", [])
        
        # Lấy danh sách bảng vật lý và số dòng từ file sqlite
        physical_tables = []
        try:
            db_file = cfg.get("db_file")
            if db_file and os.path.exists(db_file):
                conn = sqlite3.connect(db_file)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                t_names = [r[0] for r in cur.fetchall()]
                for t in t_names:
                    cur.execute(f"PRAGMA table_info('{t}');")
                    cols = [c[1] for c in cur.fetchall()]
                    cur.execute(f"SELECT COUNT(*) FROM '{t}';")
                    cnt = cur.fetchone()[0]
                    physical_tables.append({
                        "name": t,
                        "columns": cols,
                        "row_count": cnt
                    })
                conn.close()
        except Exception:
            pass

        r_info = reduction_map.get(db_id, {"reduction_pct": 0, "gold_joins": 0, "dummy_joins": 0})

        result.append({
            "db_id": db_id,
            "view_count": len(views),
            "views": [v.get("name") for v in views],
            "parsed_views": views,
            "physical_tables": physical_tables,
            "table_schemas": cfg.get("table_schemas", ""),
            "view_mapping_rules": cfg.get("view_mapping_rules", ""),
            "reduction_pct": round(r_info["reduction_pct"], 1),
            "gold_joins": round(r_info["gold_joins"], 2),
            "dummy_joins": round(r_info["dummy_joins"], 2),
            "samples": db_samples.get(db_id, [])
        })
    return result

@app.get("/api/experiments")
def get_experiments():
    # Bảng A: Đầy đủ các baseline của Paper (Bảng 3 trong bài báo V-SQL)
    table_a = [
        {"source": "Paper", "model": "GPT-4", "method": "TA-SQL", "sim": 62.83, "mod": 60.40, "chall": 36.11, "total": 56.17},
        {"source": "Paper", "model": "GPT-4", "method": "V-SQL", "sim": 62.84, "mod": 59.60, "chall": 37.25, "total": 56.00},
        {"source": "Paper", "model": "GPT-4", "method": "DAIL-SQL", "sim": 66.89, "mod": 44.40, "chall": 34.31, "total": 49.00},
        {"source": "Paper", "model": "GPT-4", "method": "DIN-SQL", "sim": 63.51, "mod": 43.60, "chall": 32.35, "total": 47.20},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "V-SQL", "sim": 62.16, "mod": 51.60, "chall": 40.19, "total": 52.80},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "TA-SQL", "sim": 62.90, "mod": 48.40, "chall": 36.11, "total": 50.16},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "DAIL-SQL", "sim": 60.13, "mod": 48.80, "chall": 32.35, "total": 48.80},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "DIN-SQL", "sim": 58.11, "mod": 47.60, "chall": 33.30, "total": 47.80},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "V-SQL", "sim": 58.11, "mod": 43.60, "chall": 31.37, "total": 45.40},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "TA-SQL", "sim": 56.75, "mod": 42.80, "chall": 27.45, "total": 43.80},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "DIN-SQL", "sim": 49.32, "mod": 39.60, "chall": 23.52, "total": 39.20},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "DAIL-SQL", "sim": 52.03, "mod": 43.60, "chall": 23.52, "total": 42.00},
    ]

    table_a.extend(experiment_runs.paper_table_rows())

    # Bảng E0: Tái hiện Bảng 2 của Paper (Dataset Statistics BIRD mini-dev)
    dataset_stats = [
        {"difficulty": "Simple", "count": 148, "avg_joins": 0.68, "avg_tables": 1.70, "combos": 74, "paper_joins": 0.75, "paper_tables": 2.30, "paper_combos": 50},
        {"difficulty": "Moderate", "count": 250, "avg_joins": 1.14, "avg_tables": 2.16, "combos": 96, "paper_joins": 1.16, "paper_tables": 2.62, "paper_combos": 86},
        {"difficulty": "Challenging", "count": 102, "avg_joins": 1.39, "avg_tables": 2.42, "combos": 57, "paper_joins": 1.35, "paper_tables": 2.76, "paper_combos": 54},
        {"difficulty": "TOTAL", "count": 500, "avg_joins": 1.06, "avg_tables": 2.08, "combos": 158, "paper_joins": 1.08, "paper_tables": 2.55, "paper_combos": 190}
    ]

    # Đối chiếu cách thực nghiệm của nhóm với bài báo
    model_comparison = [
        {"aspect": "Mô hình chính", "paper": "GPT-3.5-turbo / GPT-4 / GPT-4-turbo", "ours": "Qwen3 4B, Qwen2.5-Coder 7B và 32B, GPT-6 Luna", "verdict": "Model của paper đã ngừng hoạt động nên không tái lập được đúng model"},
        {"aspect": "Môi trường triển khai", "paper": "API của OpenAI", "ours": "Qwen chạy cục bộ, Luna qua API", "verdict": "Qwen chạy được không cần internet, Luna thì cần"},
        {"aspect": "Chi phí tài chính", "paper": "API trả phí của OpenAI", "ours": "Qwen không tốn tiền API, Luna dưới 1 USD cho toàn bộ thực nghiệm", "verdict": "Qwen đổi tiền API lấy thời gian: 500 câu trên 32B mất khoảng 3.7 giờ"},
        {"aspect": "Dữ liệu ra ngoài", "paper": "Schema và câu hỏi được gửi tới API", "ours": "Qwen giữ trên máy, Luna gửi schema và câu hỏi tới API", "verdict": "Chỉ các lần chạy Qwen giữ dữ liệu trong máy"},
        {"aspect": "Quy mô tham số", "paper": "OpenAI không công bố", "ours": "Qwen 4B, 7B và 32B tham số. Luna không công bố", "verdict": "Xem bảng cấu hình chính để so sánh theo từng model"},
        {"aspect": "Độ ổn định & Tái lập", "paper": "Phụ thuộc phiên bản model của nhà cung cấp", "ours": "temperature=0, trace từng câu được lưu và phát lại được", "verdict": "Qwen cục bộ giữ cố định phiên bản model, Luna qua API thì không"},
    ]

    return {
        "table_a": table_a,
        "dataset_stats": dataset_stats,
        "model_comparison": model_comparison,
    }

@app.get("/api/questions")
def get_questions(db: Optional[str] = None, difficulty: Optional[str] = None, search: Optional[str] = None, limit: int = 500, run: str = "luna_500_paper"):
    try:
        traces = experiment_runs.load_traces(run)
        mechanism = experiment_runs.run_mechanism(run)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    direct_trace = traces["direct"]
    vsql_trace = traces["vsql"]
    em_by_question = mechanism["em_by_question"] if mechanism else {}

    items = []
    for q in ALL_QUESTIONS:
        qid = q.get("question_id")
        q_db = q.get("db_id")
        q_diff = q.get("difficulty")
        q_text = q.get("question", "")

        if db and db != "all" and q_db != db:
            continue
        if difficulty and difficulty != "all" and q_diff.lower() != difficulty.lower():
            continue
        if search and search.lower() not in q_text.lower():
            continue

        d_item = direct_trace.get(qid, {})
        v_item = vsql_trace.get(qid, {})
        em = em_by_question.get(qid, {})

        items.append({
            "question_id": qid,
            "db_id": q_db,
            "difficulty": q_diff,
            "question": q_text,
            "evidence": q.get("evidence", ""),
            "gold_sql": q.get("SQL", ""),
            "gold_joins": d_item.get("gold_joins", 0),
            "direct": {
                "final_sql": d_item.get("final_sql", ""),
                "joins": d_item.get("trace", {}).get("joins", 0),
                "tokens": d_item.get("trace", {}).get("tokens", 0),
                "latency_s": d_item.get("trace", {}).get("latency_s", 0),
                "em_strict": em.get("direct", {}).get("strict", 0),
                "em_norm": em.get("direct", {}).get("norm", 0),
            },
            "vsql": {
                "dummy_sql": v_item.get("trace", {}).get("stage1", {}).get("dummy_sql", ""),
                "dummy_joins": v_item.get("trace", {}).get("stage1", {}).get("joins", 0),
                "final_sql": v_item.get("final_sql", ""),
                "final_joins": v_item.get("trace", {}).get("stage2", {}).get("joins", 0),
                "view_leak": v_item.get("trace", {}).get("stage2", {}).get("view_leak", False),
                "used_views": v_item.get("trace", {}).get("stage2", {}).get("used_views", []),
                "latency_s": (v_item.get("trace", {}).get("stage1", {}).get("latency_s", 0) +
                              v_item.get("trace", {}).get("stage2", {}).get("latency_s", 0)),
                "em_strict": em.get("vsql", {}).get("strict", 0),
                "em_norm": em.get("vsql", {}).get("norm", 0),
            }
        })
        if len(items) >= limit:
            break

    return {"total": len(items), "questions": items}

@app.post("/api/infer")
def run_infer(req: InferRequest):
    if req.db_id not in DB_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Database {req.db_id} not found.")

    db_cfg = DB_CONFIGS[req.db_id]
    start_time = time.perf_counter()

    if req.method == "direct":
        final_sql, trace_info = run_direct_baseline_inference(
            question=req.question,
            db_config=db_cfg,
            evidence=req.evidence or ""
        )
        total_time = round(time.perf_counter() - start_time, 2)
        exec_res = execute_sqlite_query(req.db_id, final_sql)

        return {
            "method": "direct",
            "db_id": req.db_id,
            "question": req.question,
            "evidence": req.evidence,
            "final_sql": final_sql,
            "joins": count_joins(final_sql),
            "tokens": trace_info.get("tokens", 0),
            "latency_s": total_time,
            "execution": exec_res
        }
    else:
        dummy_sql, final_sql, trace_info = run_v_sql_inference(
            question=req.question,
            db_config=db_cfg,
            evidence=req.evidence or ""
        )
        total_time = round(time.perf_counter() - start_time, 2)
        exec_res = execute_sqlite_query(req.db_id, final_sql)

        s1 = trace_info.get("stage1", {})
        s2 = trace_info.get("stage2", {})

        return {
            "method": "vsql",
            "db_id": req.db_id,
            "question": req.question,
            "evidence": req.evidence,
            "stage1": {
                "dummy_sql": dummy_sql,
                "joins": s1.get("joins", 0),
                "tokens": s1.get("tokens", 0),
                "latency_s": round(s1.get("latency_s", 0), 2),
                "view_schema": db_cfg.get("view_schema", "")
            },
            "stage2": {
                "final_sql": final_sql,
                "joins": s2.get("joins", 0),
                "tokens": s2.get("tokens", 0),
                "latency_s": round(s2.get("latency_s", 0), 2),
                "used_views": s2.get("used_views", []),
                "view_leak": s2.get("view_leak", False)
            },
            "total_latency_s": total_time,
            "execution": exec_res
        }

# Phục vụ Frontend React (nếu đã build trong frontend/dist)
dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.exists(dist_dir):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        target = os.path.join(dist_dir, full_path)
        if full_path and os.path.exists(target) and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(dist_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Khởi chạy V-SQL Studio tại http://127.0.0.1:{config.API_PORT}")
    uvicorn.run(app, host="127.0.0.1", port=config.API_PORT)
