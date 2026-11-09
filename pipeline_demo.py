"""Runs Direct and V-SQL question by question and records every step's input and output for the demo page.

Live and replay share one code path: replay only swaps the model call for the stored answer, so its prompts,
Schema Linking, SQL execution and scoring are computed for real.
"""
import dataclasses
import functools
import json
import math
import os
import random
import threading
import time
import uuid

import config
import experiment_runs
import model_registry
from llm_client import call_llm
from run_experiment import load_db_configs
from sql_eval import EvalContext, execute_query
from sql_utils import canonical_sql
from v_sql_pipeline_LLM import run_direct_baseline_inference, run_v_sql_inference

FULL_EVENT_LIMIT = 20
MAX_CONSECUTIVE_ERRORS = 3
MAX_BUDGET_USD = 1.0
DEFAULT_BUDGET_USD = 0.25
AVG_COMPLETION_TOKENS = 110
DIFFICULTIES = ("simple", "moderate", "challenging")
VIEW_LABELS = {"manual": "View thủ công", "paper": "View gold chọn lọc theo bài báo", "fk": "View mở rộng theo khóa ngoại", "gold": "View mở rộng theo gold SQL"}
CLASS_LABELS = {
    "wrong_values": "giá trị không khớp",
    "wrong_column_count": "số cột không khớp",
    "no such column": "cột không tồn tại",
    "no such table": "bảng không tồn tại",
    "no such function": "hàm không tồn tại",
    "syntax": "lỗi cú pháp",
    "other_error": "lỗi khi chạy",
    "timeout": "quá 30 giây",
    "too_many_rows": "quá nhiều dòng",
}


class RunBusy(Exception):
    pass


class RunStopped(Exception):
    pass


@dataclasses.dataclass
class RunRequest:
    selection: dict
    frameworks: list
    source: str = "live"
    model: str | None = None
    view_mode: str = "manual"
    schema_mode: str = "described"
    replay_run: str | None = None
    budget_usd: float = DEFAULT_BUDGET_USD
    step_delay_s: float = 0.0


def load_questions() -> list[dict]:
    with open(config.DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def select_questions(questions: list[dict], selection: dict) -> list[dict]:
    mode = selection.get("mode", "all")
    if mode == "all":
        return list(questions)
    if mode == "ids":
        wanted = set(selection.get("ids", []))
        return [q for q in questions if q["question_id"] in wanted]
    db, difficulty = selection.get("db"), selection.get("difficulty")
    search = (selection.get("search") or "").lower()
    picked = [
        q for q in questions
        if (not db or db == "all" or q["db_id"] == db)
        and (not difficulty or difficulty == "all" or q["difficulty"] == difficulty)
        and (not search or search in q["question"].lower())
    ]
    limit = selection.get("limit")
    if limit is not None and limit < len(picked):
        seed = selection.get("seed")
        picked = random.Random(seed).sample(picked, int(limit)) if seed is not None else picked[: int(limit)]
        picked.sort(key=lambda q: q["question_id"])
    return picked


@functools.lru_cache(maxsize=8)
def db_configs(view_mode: str, schema_mode: str) -> dict:
    return load_db_configs(views_dir=config.VIEWS_DIR, view_mode=view_mode, schema_mode=schema_mode)


def estimate(request: RunRequest, questions: list[dict]) -> dict:
    picked = select_questions(questions, request.selection)
    configs = db_configs(request.view_mode, request.schema_mode)
    calls = prompt_chars = 0
    for q in picked:
        cfg = configs[q["db_id"]]
        question_chars = len(q["question"]) + len(q.get("evidence") or "") + 400
        if "direct" in request.frameworks:
            calls += 1
            prompt_chars += len(cfg.get("direct_schema") or cfg["table_schemas"]) + question_chars
        if "vsql" in request.frameworks:
            calls += 2
            # Stage 2 sees only the linked views and tables, so about a third of the schema is typical.
            prompt_chars += len(cfg["view_schema"]) + question_chars
            prompt_chars += (len(cfg["view_mapping_rules"]) + len(cfg["table_schemas"])) // 3 + question_chars
    prompt_tokens = prompt_chars // 4
    completion_tokens = calls * AVG_COMPLETION_TOKENS
    model = model_registry.MODELS[request.model] if request.model else None
    return {
        "questions": len(picked),
        "llm_calls": calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": model_registry.estimate_cost(request.model, prompt_tokens, completion_tokens) if model else 0.0,
        "seconds": calls * model["seconds_per_call"] if model else 0.0,
    }


def _text(label, value, type_="text"):
    return {"label": label, "type": type_, "value": value}


class Run:
    def __init__(self, request: RunRequest, picked: list[dict]):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.request = request
        self.questions = picked
        self.status = "queued"
        self.message = ""
        self.events = []
        self.details = {}
        self.results = {}
        self.started_at = time.time()
        self.finished_at = None
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_errors = 0
        self.consecutive_errors = 0
        self.cancel_requested = False
        self.condition = threading.Condition()
        self.light_events = len(picked) > FULL_EVENT_LIMIT
        self.frameworks = [f for f in ("direct", "vsql") if f in request.frameworks]
        self.summary = self._summary()

    def public_config(self) -> dict:
        request = dataclasses.asdict(self.request)
        request["total_questions"] = len(self.questions)
        return request

    def add_event(self, event: dict) -> None:
        with self.condition:
            event["seq"] = len(self.events)
            self.events.append(event)
            self.condition.notify_all()

    def _summary(self) -> dict:
        frameworks = {}
        by_difficulty = {level: {} for level in DIFFICULTIES}
        by_db = {}
        for framework in self.frameworks:
            rows = [(q, self.results[q["question_id"]][framework]) for q in self.questions if framework in self.results.get(q["question_id"], {})]
            correct = sum(r["ok"] for _, r in rows)
            stage1 = sum(r.get("stage1_ok", False) for _, r in rows)
            latency = sum(r["latency_s"] for _, r in rows)
            frameworks[framework] = {
                "done": len(rows),
                "correct": correct,
                "ex": round(correct / len(rows) * 100, 2) if rows else 0.0,
                "avg_latency_s": round(latency / len(rows), 2) if rows else 0.0,
            }
            if framework == "vsql":
                frameworks[framework]["stage1_correct"] = stage1
                frameworks[framework]["stage1_ex"] = round(stage1 / len(rows) * 100, 2) if rows else 0.0
                frameworks[framework]["view_leaks"] = sum(r.get("view_leak", False) for _, r in rows)
            for level in DIFFICULTIES:
                subset = [r for q, r in rows if q["difficulty"] == level]
                by_difficulty[level][framework] = {"done": len(subset), "correct": sum(r["ok"] for r in subset)}
            for q, r in rows:
                cell = by_db.setdefault(q["db_id"], {}).setdefault(framework, {"done": 0, "correct": 0})
                cell["done"] += 1
                cell["correct"] += r["ok"]
        pairs = None
        if len(self.frameworks) == 2:
            both = [r for r in list(self.results.values()) if "direct" in r and "vsql" in r]
            direct_only = sum(r["direct"]["ok"] and not r["vsql"]["ok"] for r in both)
            vsql_only = sum(r["vsql"]["ok"] and not r["direct"]["ok"] for r in both)
            discordant = direct_only + vsql_only
            p = 1.0
            if discordant:
                p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(direct_only, vsql_only) + 1)) / 2**discordant)
            pairs = {
                "n": len(both),
                "both": sum(r["direct"]["ok"] and r["vsql"]["ok"] for r in both),
                "neither": sum(not r["direct"]["ok"] and not r["vsql"]["ok"] for r in both),
                "direct_only": direct_only,
                "vsql_only": vsql_only,
                "p": p,
            }
        return {
            "total_questions": len(self.questions),
            "frameworks": frameworks,
            "by_difficulty": by_difficulty,
            "by_db": by_db,
            "pairs": pairs,
            "cost_usd": self.cost_usd,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_errors": self.llm_errors,
            "elapsed_s": round((self.finished_at or time.time()) - self.started_at, 1),
        }

    def question_rows(self) -> list[dict]:
        rows = []
        for q in self.questions:
            result = self.results.get(q["question_id"], {})
            rows.append(
                {
                    "question_id": q["question_id"],
                    "db_id": q["db_id"],
                    "difficulty": q["difficulty"],
                    "question": q["question"],
                    "results": result,
                }
            )
        return rows

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "config": self.public_config(),
            "summary": self._summary(),
            "questions": self.question_rows(),
            "event_count": len(self.events),
        }


def _reference_input(q: dict) -> list[dict]:
    items = [
        _text("Câu hỏi", q["question"]),
        _text("Evidence của BIRD", q.get("evidence") or "(không có)"),
        _text("Database", q["db_id"]),
        _text("Độ khó", q["difficulty"]),
    ]
    return items


class QuestionPipeline:
    """Runs one framework on one question and reports each step through emit(step)."""

    def __init__(self, run: Run, ctx: EvalContext, q: dict, framework: str, cfg: dict, llm, emit):
        self.run, self.ctx, self.q, self.framework, self.cfg, self.llm, self.emit = run, ctx, q, framework, cfg, llm, emit
        self.steps = {}
        self.latency = 0.0
        self.failed_call = None
        self.record = {"ok": False, "class": None, "latency_s": 0.0}

    def step(self, step_id, title, kind, status, inputs=None, outputs=None, meta=None, summary=""):
        current = self.steps.get(step_id, {})
        step = {
            "id": step_id,
            "framework": self.framework,
            "question_id": self.q["question_id"],
            "title": title,
            "kind": kind,
            "status": status,
            "inputs": inputs if inputs is not None else current.get("inputs", []),
            "outputs": outputs if outputs is not None else current.get("outputs", []),
            "meta": meta or {},
            "summary": summary,
        }
        self.steps[step_id] = step
        self.run.details[(self.q["question_id"], self.framework)] = self.steps
        self.emit(step)

    def call_model(self, prompt):
        self.run_check()
        sql, stats = self.llm(prompt)
        prompt_tokens, completion_tokens = stats.get("prompt_tokens", 0), stats.get("completion_tokens", 0)
        self.run.prompt_tokens += prompt_tokens
        self.run.completion_tokens += completion_tokens
        if self.run.request.source == "live" and self.run.request.model in model_registry.MODELS:
            self.run.cost_usd += model_registry.estimate_cost(self.run.request.model, prompt_tokens, completion_tokens)
        self.latency += stats.get("latency_s", 0.0)
        if stats.get("error"):
            self.failed_call = stats["error"]
        return sql, stats

    def run_check(self):
        if self.run.cancel_requested:
            raise RunStopped("cancelled")

    def llm_meta(self, data):
        stats = data.get("stats", {})
        meta = {
            "latency_s": stats.get("latency_s", 0.0),
            "prompt_tokens": stats.get("prompt_tokens", 0),
            "completion_tokens": stats.get("completion_tokens", 0),
            "joins": data.get("joins", 0),
        }
        if self.run.request.source == "live" and self.run.request.model in model_registry.MODELS:
            meta["cost_usd"] = model_registry.estimate_cost(self.run.request.model, meta["prompt_tokens"], meta["completion_tokens"])
        return meta

    def on_pipeline_event(self, step_id, status, data):
        titles = {"stage1": "Stage 1: Sinh Dummy SQL trên view", "linking": "Schema Linking", "stage2": "Stage 2: Tái dựng SQL trên bảng gốc", "direct": "Sinh SQL trực tiếp"}
        if step_id == "linking":
            self.step(
                "linking", titles[step_id], "transform", "done",
                inputs=[_text("Dummy SQL", data["dummy_sql"], "sql")],
                outputs=[
                    _text("View được dùng", data["used_views"], "chips"),
                    _text("Định nghĩa của các view này", data["view_rules"], "sql"),
                    _text("Bảng gốc liên quan", data["tables"], "sql"),
                ],
                summary=f"{len(data['used_views'])} view được giữ lại",
            )
            return
        if status == "running":
            self.step(step_id, titles[step_id], "llm", "running", inputs=[_text("Prompt gửi model", data["prompt"], "prompt")], outputs=[], summary="Đang gọi model")
            return
        stats = data["stats"]
        error = stats.get("error")
        outputs = [_text("SQL sau khi làm sạch", data["sql"], "sql")]
        if stats.get("raw_content") and stats["raw_content"].strip() != data["sql"]:
            outputs.append(_text("Phản hồi thô của model", stats["raw_content"], "code"))
        if error:
            outputs.insert(0, _text("Lỗi khi gọi model", error, "error"))
        if data.get("view_leak"):
            outputs.append(_text("Cảnh báo", "SQL cuối còn tham chiếu tên view (view leak)", "warning"))
        meta = self.llm_meta(data)
        if "view_leak" in data:
            meta["view_leak"] = data["view_leak"]
        self.step(
            step_id, titles[step_id], "llm", "error" if error else "done", outputs=outputs, meta=meta,
            summary=f"{meta['joins']} JOIN, {meta['latency_s']:.1f}s" if not error else "Lỗi khi gọi model",
        )

    def run_all(self):
        q, cfg = self.q, self.cfg
        augmented = f"{q['question']}\nEvidence: {q['evidence'].strip()}" if (q.get("evidence") or "").strip() else q["question"]
        self.step("input", "Đầu vào từ BIRD mini-dev", "input", "done", inputs=_reference_input(q), outputs=[_text("Câu hỏi đưa vào prompt", augmented)], summary="Đã nạp câu hỏi")
        self.pace()

        request = self.run.request
        if self.framework == "vsql":
            views = cfg["parsed_views"]
            columns = sum(len(v["columns"]) for v in views)
            self.step(
                "mapping", "Table Mapping: Chuẩn bị schema view", "transform", "done",
                inputs=[_text("Bộ view", VIEW_LABELS.get(request.view_mode, request.view_mode)), _text("Schema bảng gốc", cfg["table_schemas"], "sql")],
                outputs=[_text("Schema view đưa vào Stage 1", cfg["view_schema"], "code")],
                meta={"views": len(views), "view_columns": columns},
                summary=f"{len(views)} view, {columns} cột",
            )
            self.pace()
            dummy, final, trace = self.run_vsql()
            self.record.update(dummy_sql=dummy, final_sql=final, view_leak=trace["stage2"]["view_leak"], used_views=trace["stage2"]["used_views"], stage1_joins=trace["stage1"]["joins"], final_joins=trace["stage2"]["joins"])
        else:
            schema = cfg.get("direct_schema") or cfg["table_schemas"]
            self.step(
                "mapping", "Chuẩn bị schema bảng gốc", "transform", "done",
                inputs=[_text("Schema bảng gốc trong database", cfg["table_schemas"], "sql")],
                outputs=[_text("Schema đưa vào prompt", schema, "code")],
                meta={"schema_mode": request.schema_mode},
                summary="Có mô tả cột" if request.schema_mode == "described" else "Chỉ có DDL",
            )
            self.pace()
            final, trace = run_direct_baseline_inference(q["question"], cfg, q.get("evidence") or "", llm=self.call_model, on_event=self.on_event_with_pace)
            self.record.update(final_sql=final, final_joins=trace["joins"])
        self.execute_and_score(final)
        self.record["latency_s"] = round(self.latency, 3)
        return self.record

    def on_event_with_pace(self, step_id, status, data):
        self.on_pipeline_event(step_id, status, data)
        if status == "done":
            self.pace()

    def pace(self):
        self.run_check()
        delay = self.run.request.step_delay_s
        if delay:
            time.sleep(delay)
            self.run_check()

    def run_vsql(self):
        q, cfg = self.q, self.cfg

        def on_event(step_id, status, data):
            if step_id == "linking":
                self.stage1_execution(data["dummy_sql"])
            self.on_event_with_pace(step_id, status, data)

        return run_v_sql_inference(q["question"], cfg, q.get("evidence") or "", llm=self.call_model, on_event=on_event)

    def stage1_execution(self, dummy_sql):
        q, cfg = self.q, self.cfg
        con = self.ctx.views(q["db_id"], self.run.request.view_mode, cfg["parsed_views"])
        result = execute_query(con, dummy_sql)
        verdict = self.ctx.compare(q, result)
        self.record["stage1_ok"] = verdict["ok"]
        self.record["stage1_class"] = verdict["class"]
        self.step(
            "stage1_exec", "Kiểm tra Dummy SQL trên view tạm", "execute", "error" if result.error else "done",
            inputs=[_text("Dummy SQL", dummy_sql, "sql"), _text("Nơi chạy", "View tạm trong kết nối chỉ đọc, không ghi vào database")],
            outputs=[_text("Kết quả", result.public(), "rows"), _text("So với đáp án gold", verdict, "verdict")],
            meta={"seconds": round(result.seconds, 3), "matches_gold": verdict["ok"]},
            summary=("Lỗi: " + result.error[:70]) if result.error else ("Khớp gold" if verdict["ok"] else "Chạy được, chưa khớp gold"),
        )
        self.pace()

    def execute_and_score(self, final_sql):
        q = self.q
        self.step("execute", "Thực thi SQL cuối trên bảng gốc", "execute", "running", inputs=[_text("SQL cuối", final_sql, "sql")], outputs=[], summary="Đang chạy")
        result = execute_query(self.ctx.physical(q["db_id"]), final_sql)
        self.step(
            "execute", "Thực thi SQL cuối trên bảng gốc", "execute", "error" if result.error else "done",
            outputs=[_text("Kết quả", result.public(), "rows")],
            meta={"seconds": round(result.seconds, 3), "rows": result.total_rows},
            summary=("Lỗi: " + result.error[:70]) if result.error else f"{result.total_rows} dòng",
        )
        self.pace()
        gold = self.ctx.gold(q)
        verdict = self.ctx.compare(q, result)
        em = canonical_sql(final_sql) == canonical_sql(q["SQL"])
        self.record.update(ok=verdict["ok"], **{"class": verdict["class"]}, error=verdict["error"], em_normalized=em)
        self.step(
            "score", "Chấm Execution Accuracy", "score", "done",
            inputs=[_text("SQL cuối", final_sql, "sql"), _text("Gold SQL", q["SQL"], "sql"), _text("Kết quả gold", gold.public(), "rows")],
            outputs=[_text("Kết luận", verdict, "verdict"), _text("Khớp SQL sau chuẩn hóa (EM)", "Có" if em else "Không")],
            meta={"ok": verdict["ok"], "class": verdict["class"]},
            summary="Đúng" if verdict["ok"] else f"Sai: {CLASS_LABELS.get(verdict['class'], verdict['class'])}",
        )


def _replay_llm(framework: str, record: dict):
    if framework == "direct":
        calls = [(record["final_sql"], record["trace"])]
    else:
        trace = record["trace"]
        calls = [(trace["stage1"]["dummy_sql"], trace["stage1"]), (trace["stage2"]["final_sql"], trace["stage2"])]
    remaining = iter(calls)

    def llm(prompt):
        sql, trace = next(remaining)
        return sql, {
            "prompt_tokens": trace.get("prompt_tokens", 0),
            "completion_tokens": trace.get("tokens", 0),
            "latency_s": trace.get("latency_s", 0.0),
            "raw_content": sql,
            "error": trace.get("error"),
        }

    return llm


class RunManager:
    def __init__(self, llm_factory=None, save_runs=False):
        self.llm_factory = llm_factory
        self.save_runs = save_runs
        self.runs = {}
        self.lock = threading.Lock()
        self.questions = load_questions()

    def start(self, request: RunRequest) -> Run:
        if request.source == "replay":
            return self._start_replay(request)
        return self._start_live(request)

    def _prepare(self, request, picked, traces):
        if not picked:
            raise ValueError("Không có câu hỏi nào khớp lựa chọn")
        if not request.frameworks:
            raise ValueError("Chọn ít nhất một framework")
        run = Run(request, picked)
        with self.lock:
            self.runs[run.id] = run
        thread = threading.Thread(target=self._execute, args=(run, traces), daemon=True)
        thread.start()
        return run

    def _start_live(self, request):
        if request.model not in model_registry.MODELS:
            raise ValueError("Model không hợp lệ")
        if request.view_mode not in VIEW_LABELS:
            raise ValueError("Bộ view không hợp lệ")
        request.budget_usd = min(max(float(request.budget_usd), 0.0), MAX_BUDGET_USD)
        with self.lock:
            if any(r.request.source == "live" and r.status in ("queued", "running") for r in self.runs.values()):
                raise RunBusy("Đang có một lần chạy thật, hãy đợi hoặc dừng nó trước")
        return self._prepare(request, select_questions(self.questions, request.selection), None)

    def _start_replay(self, request):
        stored = experiment_runs.run_config(request.replay_run)
        traces = experiment_runs.load_traces(request.replay_run)
        request.view_mode, request.schema_mode, request.model = stored["view_mode"], stored["schema_mode"], None
        request.frameworks = [f for f in request.frameworks if traces.get(f)]
        have = set.union(*(set(traces[f]) for f in request.frameworks)) if request.frameworks else set()
        picked = [q for q in select_questions(self.questions, request.selection) if all(q["question_id"] in traces[f] for f in request.frameworks)]
        if not picked:
            raise ValueError(f"Lần chạy {request.replay_run} không có các câu đã chọn ({len(have)} câu đã lưu)")
        return self._prepare(request, picked, traces)

    def cancel(self, run_id: str) -> None:
        run = self.runs.get(run_id)
        if run:
            run.cancel_requested = True

    def _llm_for(self, run, q, framework, traces):
        if traces is not None:
            return _replay_llm(framework, traces[framework][q["question_id"]])
        if self.llm_factory:
            return self.llm_factory(run.request, q, framework)
        profile = model_registry.get_profile(run.request.model)
        return lambda prompt: call_llm(prompt=prompt, temperature=config.TEMPERATURE, max_tokens=config.MAX_TOKENS, top_p=config.TOP_P, profile=profile)

    def _execute(self, run: Run, traces) -> None:
        run.status = "running"
        run.add_event({"type": "run_start", "run_id": run.id, "config": run.public_config()})
        ctx = EvalContext()
        try:
            configs = db_configs(run.request.view_mode, run.request.schema_mode)
            for index, q in enumerate(run.questions):
                run.add_event({"type": "question_start", "question": {k: q.get(k) for k in ("question_id", "db_id", "difficulty", "question", "evidence")}, "index": index, "total": len(run.questions)})
                for framework in run.frameworks:
                    self._run_one(run, ctx, q, framework, configs[q["db_id"]], traces)
                    if run.request.source == "live" and run.cost_usd >= run.request.budget_usd and self._more_work(run, q, framework):
                        run.status = "budget_stopped"
                        run.message = f"Đã chạm hạn mức ${run.request.budget_usd:.2f}"
                        raise RunStopped("budget")
            run.status = "done"
        except RunStopped as stop:
            if str(stop) == "cancelled":
                run.status = "cancelled"
                run.message = "Đã dừng theo yêu cầu"
        except Exception as exc:
            run.status = "error"
            run.message = run.message or str(exc)
        finally:
            ctx.close()
            run.finished_at = time.time()
            run.summary = run._summary()
            run.add_event({"type": "run_done", "status": run.status, "message": run.message, "summary": run.summary})
            if self.save_runs and run.request.source == "live":
                self._save(run)

    @staticmethod
    def _more_work(run, q, framework):
        last_question = run.questions[-1]["question_id"] == q["question_id"]
        return not (last_question and run.frameworks[-1] == framework)

    def _run_one(self, run, ctx, q, framework, cfg, traces):
        def emit(step):
            event = {"type": "step", "step": step}
            if run.light_events:
                event["step"] = {k: v for k, v in step.items() if k not in ("inputs", "outputs")}
            run.add_event(event)

        pipeline = QuestionPipeline(run, ctx, q, framework, cfg, self._llm_for(run, q, framework, traces), emit)
        record = pipeline.run_all()
        run.results.setdefault(q["question_id"], {})[framework] = record
        run.add_event({"type": "question_done", "question_id": q["question_id"], "framework": framework, "result": record, "summary": run._summary()})
        if pipeline.failed_call:
            run.llm_errors += 1
            run.consecutive_errors += 1
            if traces is None and run.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                run.message = f"Dừng sau {run.consecutive_errors} lỗi liên tiếp: {pipeline.failed_call}"
                raise RuntimeError(run.message)
        else:
            run.consecutive_errors = 0

    def _save(self, run: Run) -> None:
        out_dir = os.path.join(config.OUTPUTS_DIR, "demo_runs", run.id)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump({"status": run.status, "message": run.message, "config": run.public_config(), "summary": run.summary}, f, indent=2, ensure_ascii=False)
        with open(os.path.join(out_dir, "per_question.jsonl"), "w", encoding="utf-8") as f:
            for row in run.question_rows():
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
