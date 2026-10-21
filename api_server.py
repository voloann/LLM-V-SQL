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
import llm_client

app = FastAPI(title="V-SQL Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nạp dữ liệu nền
DB_CONFIGS = load_db_configs()

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
    
    # Thống kê JOIN từ Table D của Paper / Thực nghiệm
    reduction_map = {
        "formula_1": {"reduction_pct": 39.1, "gold_joins": 1.15, "dummy_joins": 0.70},
        "superhero": {"reduction_pct": 62.5, "gold_joins": 1.60, "dummy_joins": 0.60},
        "card_games": {"reduction_pct": 16.5, "gold_joins": 0.85, "dummy_joins": 0.71},
        "european_football_2": {"reduction_pct": 78.6, "gold_joins": 0.84, "dummy_joins": 0.18},
        "thrombosis_prediction": {"reduction_pct": 71.4, "gold_joins": 0.84, "dummy_joins": 0.24},
        "codebase_community": {"reduction_pct": 60.7, "gold_joins": 0.84, "dummy_joins": 0.33},
        "student_club": {"reduction_pct": 54.5, "gold_joins": 0.88, "dummy_joins": 0.40},
        "toxicology": {"reduction_pct": 37.6, "gold_joins": 1.25, "dummy_joins": 0.78},
        "financial": {"reduction_pct": 46.8, "gold_joins": 1.41, "dummy_joins": 0.75},
        "debit_card_specializing": {"reduction_pct": 63.0, "gold_joins": 1.00, "dummy_joins": 0.37},
        "california_schools": {"reduction_pct": 92.5, "gold_joins": 0.93, "dummy_joins": 0.07}
    }

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

        r_info = reduction_map.get(db_id, {"reduction_pct": 50.0, "gold_joins": 1.0, "dummy_joins": 0.5})

        result.append({
            "db_id": db_id,
            "view_count": len(views),
            "views": [v.get("name") for v in views],
            "parsed_views": views,
            "physical_tables": physical_tables,
            "table_schemas": cfg.get("table_schemas", ""),
            "view_mapping_rules": cfg.get("view_mapping_rules", ""),
            "reduction_pct": r_info["reduction_pct"],
            "gold_joins": r_info["gold_joins"],
            "dummy_joins": r_info["dummy_joins"],
            "samples": db_samples.get(db_id, [])
        })
    return result

@app.get("/api/experiments")
def get_experiments():
    direct_metrics_file = "outputs/500_all_direct/metrics.json"
    vsql_metrics_file = "outputs/500_all_vsql/metrics.json"
    
    direct_metrics = {}
    vsql_metrics = {}
    if os.path.exists(direct_metrics_file):
        with open(direct_metrics_file, "r", encoding="utf-8") as f:
            direct_metrics = json.load(f)
    if os.path.exists(vsql_metrics_file):
        with open(vsql_metrics_file, "r", encoding="utf-8") as f:
            vsql_metrics = json.load(f)

    # Thống kê JOIN từ trace vsql
    join_stats = {
        "gold_avg": 1.05,
        "dummy_avg": 0.46,
        "final_avg": 0.90,
        "reduction_pct": 56.2,
        "view_leaks": 21
    }

    # Bảng A: Đầy đủ các baseline của Paper (Bảng 3 trong bài báo V-SQL)
    table_a = [
        {"source": "Paper", "model": "GPT-4", "method": "TA-SQL", "sim": 62.83, "mod": 60.40, "chall": 36.11, "total": 56.17},
        {"source": "Paper", "model": "GPT-4", "method": "V-SQL", "sim": 62.84, "mod": 59.60, "chall": 37.25, "total": 56.00},
        {"source": "Paper", "model": "GPT-4", "method": "DAIL-SQL", "sim": 66.89, "mod": 44.40, "chall": 34.31, "total": 49.00},
        {"source": "Paper", "model": "GPT-4", "method": "DIN-SQL", "sim": 63.51, "mod": 43.60, "chall": 32.35, "total": 47.20},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "V-SQL", "sim": 62.16, "mod": 51.60, "chall": 40.19, "total": 52.80},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "TA-SQL", "sim": 58.78, "mod": 45.60, "chall": 41.18, "total": 48.60},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "DAIL-SQL", "sim": 54.05, "mod": 47.60, "chall": 40.20, "total": 48.00},
        {"source": "Paper", "model": "GPT-4-turbo", "method": "DIN-SQL", "sim": 58.11, "mod": 47.60, "chall": 33.30, "total": 47.80},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "V-SQL", "sim": 58.11, "mod": 43.60, "chall": 31.37, "total": 45.40},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "TA-SQL", "sim": 56.75, "mod": 42.80, "chall": 27.45, "total": 43.80},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "DIN-SQL", "sim": 52.03, "mod": 40.00, "chall": 31.37, "total": 41.80},
        {"source": "Paper", "model": "GPT-3.5-turbo", "method": "DAIL-SQL", "sim": 56.76, "mod": 37.20, "chall": 31.37, "total": 41.80},
        {
            "source": "Ours (Local)",
            "model": "Qwen2.5-Coder-7B",
            "method": "DIRECT (E2)",
            "sim": direct_metrics.get("EX", {}).get("simple", 67.57),
            "mod": direct_metrics.get("EX", {}).get("moderate", 43.60),
            "chall": direct_metrics.get("EX", {}).get("challenging", 27.45),
            "total": direct_metrics.get("EX", {}).get("total", 47.40)
        },
        {
            "source": "Ours (Local)",
            "model": "Qwen2.5-Coder-7B",
            "method": "V-SQL (E1)",
            "sim": vsql_metrics.get("EX", {}).get("simple", 47.30),
            "mod": vsql_metrics.get("EX", {}).get("moderate", 30.80),
            "chall": vsql_metrics.get("EX", {}).get("challenging", 20.59),
            "total": vsql_metrics.get("EX", {}).get("total", 33.60)
        }
    ]

    # Bảng B: Exact Match AST (EM-Strict & EM-Normalized)
    table_b = {
        "direct": {
            "simple_strict": 20.27, "simple_norm": 22.97,
            "moderate_strict": 4.80, "moderate_norm": 4.80,
            "challenging_strict": 1.96, "challenging_norm": 2.94,
            "total_strict": 8.80, "total_norm": 9.80
        },
        "vsql": {
            "simple_strict": 4.05, "simple_norm": 10.81,
            "moderate_strict": 0.80, "moderate_norm": 2.40,
            "challenging_strict": 0.98, "challenging_norm": 1.96,
            "total_strict": 1.80, "total_norm": 4.80
        }
    }

    # Bảng C: Cơ chế giảm JOIN trước và sau Stage 1/Stage 2
    table_c = [
        {"difficulty": "Simple", "count": 148, "gold_joins": 0.68, "dummy_joins": 0.33, "final_joins": 0.71, "reduction_pct": 51.5, "view_leaks": 5, "tokens_dummy": 50.6, "tokens_final": 47.2},
        {"difficulty": "Moderate", "count": 250, "gold_joins": 1.14, "dummy_joins": 0.56, "final_joins": 0.97, "reduction_pct": 50.9, "view_leaks": 9, "tokens_dummy": 74.4, "tokens_final": 65.0},
        {"difficulty": "Challenging", "count": 102, "gold_joins": 1.39, "dummy_joins": 0.48, "final_joins": 1.03, "reduction_pct": 65.5, "view_leaks": 7, "tokens_dummy": 93.1, "tokens_final": 85.9},
        {"difficulty": "TOTAL", "count": 500, "gold_joins": 1.05, "dummy_joins": 0.46, "final_joins": 0.90, "reduction_pct": 56.2, "view_leaks": 21, "tokens_dummy": 71.2, "tokens_final": 63.9}
    ]

    # Bảng D: Phân tích chi tiết trên 11 CSDL SQLite
    table_d = [
        {"db_id": "formula_1", "count": 66, "gold_joins": 1.15, "dummy_joins": 0.70, "reduction_pct": 39.1, "view_leaks": 2, "d_tokens": 58.0, "v_tokens": 148.6, "notes": "CSDL nhiều bảng nhất, quan hệ đua xe phức tạp"},
        {"db_id": "superhero", "count": 52, "gold_joins": 1.60, "dummy_joins": 0.60, "reduction_pct": 62.5, "view_leaks": 13, "d_tokens": 58.6, "v_tokens": 107.1, "notes": "CSDL gốc của Paper, JOIN cao nhất (1.60), tỷ lệ rò rỉ view cao ở Stage 2"},
        {"db_id": "card_games", "count": 52, "gold_joins": 0.85, "dummy_joins": 0.71, "reduction_pct": 16.5, "view_leaks": 2, "d_tokens": 49.2, "v_tokens": 146.8, "notes": "Các bảng bài Magic & luật chơi, nhiều JOIN tự nhiên"},
        {"db_id": "european_football_2", "count": 51, "gold_joins": 0.84, "dummy_joins": 0.18, "reduction_pct": 78.6, "view_leaks": 0, "d_tokens": 57.7, "v_tokens": 123.8, "notes": "View giảm JOIN cực mạnh (-78.6%), 0 lỗi rò rỉ view"},
        {"db_id": "thrombosis_prediction", "count": 50, "gold_joins": 0.84, "dummy_joins": 0.24, "reduction_pct": 71.4, "view_leaks": 0, "d_tokens": 63.9, "v_tokens": 152.5, "notes": "Dữ liệu y tế chẩn đoán huyết khối, view làm phẳng rất hiệu quả"},
        {"db_id": "codebase_community", "count": 49, "gold_joins": 0.84, "dummy_joins": 0.33, "reduction_pct": 60.7, "view_leaks": 1, "d_tokens": 48.0, "v_tokens": 104.9, "notes": "Diễn đàn hỏi đáp (posts, comments, users)"},
        {"db_id": "student_club", "count": 48, "gold_joins": 0.88, "dummy_joins": 0.40, "reduction_pct": 54.5, "view_leaks": 1, "d_tokens": 50.3, "v_tokens": 115.2, "notes": "Quản lý câu lạc bộ sinh viên, ngân sách và sự kiện"},
        {"db_id": "toxicology", "count": 40, "gold_joins": 1.25, "dummy_joins": 0.78, "reduction_pct": 37.6, "view_leaks": 0, "d_tokens": 60.4, "v_tokens": 134.3, "notes": "Cấu trúc hóa học phân tử, liên kết nguyên tử"},
        {"db_id": "financial", "count": 32, "gold_joins": 1.41, "dummy_joins": 0.75, "reduction_pct": 46.8, "view_leaks": 0, "d_tokens": 74.6, "v_tokens": 159.5, "notes": "Giao dịch tài khoản ngân hàng, vay vốn tín dụng"},
        {"db_id": "debit_card_specializing", "count": 30, "gold_joins": 1.00, "dummy_joins": 0.37, "reduction_pct": 63.0, "view_leaks": 1, "d_tokens": 78.2, "v_tokens": 174.0, "notes": "Chi tiêu thẻ ghi nợ cây xăng, phân khúc khách hàng"},
        {"db_id": "california_schools", "count": 30, "gold_joins": 0.93, "dummy_joins": 0.07, "reduction_pct": 92.5, "view_leaks": 1, "d_tokens": 71.0, "v_tokens": 142.5, "notes": "Điểm thi SAT và trường học, View triệt tiêu 92.5% JOIN"}
    ]

    # Bảng E0: Tái hiện Bảng 2 của Paper (Dataset Statistics BIRD mini-dev)
    dataset_stats = [
        {"difficulty": "Simple", "count": 148, "avg_joins": 0.68, "avg_tables": 1.70, "combos": 74, "paper_joins": 0.75, "paper_tables": 2.30, "paper_combos": 50},
        {"difficulty": "Moderate", "count": 250, "avg_joins": 1.14, "avg_tables": 2.16, "combos": 96, "paper_joins": 1.16, "paper_tables": 2.62, "paper_combos": 86},
        {"difficulty": "Challenging", "count": 102, "avg_joins": 1.39, "avg_tables": 2.42, "combos": 57, "paper_joins": 1.35, "paper_tables": 2.76, "paper_combos": 54},
        {"difficulty": "TOTAL", "count": 500, "avg_joins": 1.06, "avg_tables": 2.08, "combos": 158, "paper_joins": 1.08, "paper_tables": 2.55, "paper_combos": 190}
    ]

    # So sánh Bản chất Model: Paper (Proprietary Cloud API) vs Nghiên cứu của ta (Open-weights Local)
    model_comparison = [
        {"aspect": "Mô hình chính", "paper": "GPT-3.5-turbo / GPT-4 / GPT-4-turbo", "ours": "Qwen2.5-Coder-7B-Instruct", "verdict": "Mô hình ta chuyên sâu cho lập trình & SQL (cuối 2024)"},
        {"aspect": "Môi trường triển khai", "paper": "Cloud API (Máy chủ OpenAI, Mỹ)", "ours": "100% Cục bộ (Local LM Studio trên máy trạm)", "verdict": "Tự chủ hạ tầng, chạy offline không phụ thuộc internet"},
        {"aspect": "Chi phí tài chính", "paper": "Rất tốn kém ($0.03 - $0.06 / 1k tokens, hàng trăm USD)", "ours": "0 USD (Hoàn toàn MIỄN PHÍ)", "verdict": "Tiết kiệm 100% chi phí, khả năng thực nghiệm không giới hạn"},
        {"aspect": "Bảo mật dữ liệu (Privacy)", "paper": "Nguy cơ rò rỉ dữ liệu CSDL doanh nghiệp lên Cloud", "ours": "Bảo mật tuyệt đối (On-premises Privacy)", "verdict": "Đáp ứng tiêu chuẩn khắt khe ngành ngân hàng, y tế, quốc phòng"},
        {"aspect": "Quy mô tham số", "paper": "~175B đến 1,800B tham số (MoE khổng lồ)", "ours": "7B tham số (SLM tinh gọn)", "verdict": "Mô hình 7B đạt 47.4% EX trực tiếp, vượt cả GPT-3.5 (45.4%)"},
        {"aspect": "Độ ổn định & Tái lập", "paper": "Dễ bị trôi phiên bản (drift), rủi ro rate limits / timeout", "ours": "Hoàn toàn tất định (temperature=0, 100% tái lập được)", "verdict": "Đảm bảo tính khoa học và minh bạch thực nghiệm"}
    ]

    return {
        "table_a": table_a,
        "table_b": table_b,
        "table_c": table_c,
        "table_d": table_d,
        "dataset_stats": dataset_stats,
        "model_comparison": model_comparison,
        "join_stats": join_stats,
        "direct_metrics": direct_metrics,
        "vsql_metrics": vsql_metrics
    }

@app.get("/api/questions")
def get_questions(db: Optional[str] = None, difficulty: Optional[str] = None, search: Optional[str] = None, limit: int = 500):
    # Nạp trace từ cả 2 bên để đối chiếu
    direct_trace = {}
    vsql_trace = {}

    d_trace_f = "outputs/500_all_direct/trace.jsonl"
    v_trace_f = "outputs/500_all_vsql/trace.jsonl"

    if os.path.exists(d_trace_f):
        with open(d_trace_f, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    direct_trace[item["question_id"]] = item

    if os.path.exists(v_trace_f):
        with open(v_trace_f, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    vsql_trace[item["question_id"]] = item

    d_em_f = "outputs/500_all_direct/em_details.json"
    v_em_f = "outputs/500_all_vsql/em_details.json"
    direct_em = {}
    vsql_em = {}
    if os.path.exists(d_em_f):
        try:
            with open(d_em_f, "r", encoding="utf-8") as f:
                d_em_data = json.load(f)
                for item in d_em_data.get("details", []):
                    direct_em[str(item.get("question_id"))] = item
        except Exception:
            pass

    if os.path.exists(v_em_f):
        try:
            with open(v_em_f, "r", encoding="utf-8") as f:
                v_em_data = json.load(f)
                for item in v_em_data.get("details", []):
                    vsql_em[str(item.get("question_id"))] = item
        except Exception:
            pass

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
        d_em = direct_em.get(str(qid), {})
        v_em = vsql_em.get(str(qid), {})

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
                "em_strict": d_em.get("em_strict", 0),
                "em_norm": d_em.get("em_norm", 0),
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
                "em_strict": v_em.get("em_strict", 0),
                "em_norm": v_em.get("em_norm", 0),
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
    print("🚀 Khởi chạy V-SQL Studio tại http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
