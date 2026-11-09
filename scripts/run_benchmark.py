"""Run Direct then V-SQL on <out_dir>/questions.json, scoring each answer live on physical tables.

usage: run_benchmark.py <out_dir> <model_id> [--view-mode manual|fk|gold] [--schema-mode names|described]
                        [--budget USD] [--port N] [--label TEXT]
Models come from model_registry.py. run_experiment.py --no-eval does the inference, so a trace.jsonl already in
<out_dir> is reused and only missing questions cost money. Databases are opened read-only.
A live progress page is served on --port.
"""
import argparse, collections, http.server, json, math, os, re, sqlite3, statistics, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import model_registry
from build_views import gold_gaps, load_db_schema

_parser = argparse.ArgumentParser()
_parser.add_argument("out_dir")
_parser.add_argument("model", choices=sorted(model_registry.MODELS))
_parser.add_argument("--view-mode", default="manual", choices=["manual", "fk", "gold", "paper"])
_parser.add_argument("--schema-mode", default="described", choices=["names", "described"])
_parser.add_argument("--budget", type=float, default=1.0, help="stop when this run's new LLM calls cost more than this (USD)")
_parser.add_argument("--port", type=int, default=8765)
_parser.add_argument("--label", default=None)
ARGS = _parser.parse_args()
OUT, MODEL = os.path.abspath(ARGS.out_dir), ARGS.model
HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT, ROW_CAP, MAX_CONSEC_ERR = 30.0, 2_000_000, 3
SAMPLE = f"{OUT}/questions.json"
QS = {d["question_id"]: d for d in json.load(open(SAMPLE, encoding="utf-8"))}
BASE = {}
with open(f"{ROOT}/outputs/rescored_physical/per_question.jsonl") as fh:
    for line in fh:
        r = json.loads(line)
        if r["question_id"] in QS:
            BASE[r["question_id"]] = r
VIEWS = {}
for fn in os.listdir(f"{ROOT}/views/{ARGS.view_mode}"):
    if fn.endswith(".json"):
        with open(f"{ROOT}/views/{ARGS.view_mode}/{fn}", encoding="utf-8") as f:
            VIEWS[fn[:-5]] = json.load(f)["views"]
SPENT = {"usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0}


def execute(con, sql, limit=TIMEOUT):
    deadline = time.time() + limit
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 200000)
    try:
        cur = con.execute(sql)
        width, rows, n = len(cur.description or []), set(), 0
        while True:
            chunk = cur.fetchmany(20000)
            if not chunk:
                return rows, width, None
            rows.update(chunk)
            n += len(chunk)
            if n > ROW_CAP:
                return None, width, "too_many_rows"
    except sqlite3.OperationalError as e:
        return (None, 0, "timeout") if "interrupt" in str(e).lower() else (None, 0, str(e))
    except Exception as e:
        return None, 0, str(e)
    finally:
        con.set_progress_handler(None, 0)


PHYS, VIEWCON, GOLD = {}, {}, {}


def phys(db):
    if db not in PHYS:
        path = f"{ROOT}/mini_dev_databases/{db}/{db}.sqlite"
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        views = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='view'")]
        if views:
            mem = sqlite3.connect(":memory:")
            src.backup(mem)
            src.close()
            for v in views:
                mem.execute(f'DROP VIEW "{v}"')
            src = mem
        PHYS[db] = src
    return PHYS[db]


def viewcon(db):
    if db not in VIEWCON:
        path = f"{ROOT}/mini_dev_databases/{db}/{db}.sqlite"
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for v in VIEWS[db]:
            ddl = re.sub(r"/\*.*?\*/", "", v["create_sql"], flags=re.S).strip()
            con.execute(re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", ddl, flags=re.I))
        VIEWCON[db] = con
    return VIEWCON[db]


def gold(q):
    if q not in GOLD:
        GOLD[q] = execute(phys(QS[q]["db_id"]), QS[q]["SQL"], limit=300.0)
    return GOLD[q]


def classify(ok, err, width, gw):
    if ok:
        return "correct"
    if err in ("timeout", "too_many_rows"):
        return err
    if err:
        m = re.match(r"no such (column|table|function)", err)
        return "no such " + m.group(1) if m else ("syntax" if ("syntax" in err or "incomplete" in err) else "other_error")
    return "wrong_column_count" if width != gw else "wrong_values"


def score(q, con, sql):
    g, gw, ge = gold(q)
    s, w, e = execute(con, sql)
    ok = (s == g) and not ge
    return ok, classify(ok, e, w, gw), e


LOCK = threading.Lock()
SER = ("direct", "stage1", "vsql")
blank = lambda n: {"n": n, "direct_done": 0, "vsql_done": 0, "direct": 0, "stage1": 0, "vsql": 0}
by_db_n = collections.Counter(d["db_id"] for d in QS.values())
by_diff_n = collections.Counter(d["difficulty"] for d in QS.values())
start = time.time()
PROG = {
    "status": "running", "model": MODEL, "total": len(QS), "elapsed": 0, "phase": "direct", "current": None, "message": "",
    "done": {"direct": 0, "vsql": 0}, "ok": {k: 0 for k in SER},
    "base": {k: {"ok": 0, "n": 0} for k in SER}, "base_all": {k: sum(BASE[q][k + "_ok"] for q in BASE) for k in SER},
    "latency": {"direct": 0.0, "vsql": 0.0}, "llm_errors": 0,
    "by_db": {d: blank(by_db_n[d]) for d in sorted(by_db_n)},
    "by_diff": {d: blank(by_diff_n[d]) for d in ("simple", "moderate", "challenging")},
}
RES = {q: {"question_id": q, "db_id": QS[q]["db_id"], "difficulty": QS[q]["difficulty"]} for q in QS}
LAT = {"direct": [], "vsql": []}
PROG["median"] = {"direct": 0.0, "vsql": 0.0}


def purge_failed(path, method):
    """Drop records whose LLM call failed, so a resume retries them instead of keeping a placeholder answer."""
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        lines = [l for l in fh if l.strip()]
    keep = []
    for line in lines:
        tr = json.loads(line)["trace"]
        failed = tr.get("error") if method == "direct" else (tr["stage1"].get("error") or tr["stage2"].get("error"))
        if not failed:
            keep.append(line)
    if len(keep) != len(lines):
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(path + ".tmp", path)
    return len(lines) - len(keep)


for _m in ("direct", "vsql"):
    _n = purge_failed(f"{OUT}/{_m}/trace.jsonl", _m)
    if _n:
        print(f"purged {_n} failed records from {_m}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/progress"):
            with LOCK:
                PROG["elapsed"] = round(time.time() - start, 1)
                body, ctype = json.dumps(PROG).encode(), "application/json"
        elif self.path == "/":
            with open(f"{HERE}/run_benchmark_progress.html", "rb") as fh:
                body, ctype = fh.read(), "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


PROG["label"] = ARGS.label or f"{MODEL}, view {ARGS.view_mode}"
threading.Thread(target=http.server.ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever, daemon=True).start()


def bump(q, key, ok):
    d = QS[q]
    PROG["ok"][key] += ok
    PROG["by_db"][d["db_id"]][key] += ok
    PROG["by_diff"][d["difficulty"]][key] += ok
    PROG["base"][key]["ok"] += BASE[q][key + "_ok"]
    PROG["base"][key]["n"] += 1


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.endswith("\n"))


REUSED = {m: count_lines(f"{OUT}/{m}/trace.jsonl") for m in ("direct", "vsql")}


def add_spend(method, tr):
    calls = [tr] if method == "direct" else [tr["stage1"], tr["stage2"]]
    for call in calls:
        SPENT["prompt_tokens"] += call.get("prompt_tokens", 0)
        SPENT["completion_tokens"] += call.get("tokens", 0)
        SPENT["usd"] += model_registry.estimate_cost(MODEL, call.get("prompt_tokens", 0), call.get("tokens", 0))


def consume(method, path, seen, consec):
    if not os.path.exists(path):
        return consec
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for line in lines[seen[method]:]:
        if not line.endswith("\n"):
            break
        seen[method] += 1
        r = json.loads(line)
        q = r["question_id"]
        db = r["db_id"]
        tr = r["trace"]
        if seen[method] > REUSED[method]:
            add_spend(method, tr)
        if method == "direct":
            failed = bool(tr.get("error"))
            ok, cls, err = score(q, phys(db), r["final_sql"])
            RES[q].update(direct_ok=ok, direct_class=cls, direct_error=err, direct_sql=r["final_sql"], direct_joins=tr["joins"], direct_latency_s=tr["latency_s"], direct_tokens=tr["tokens"])
            with LOCK:
                PROG["done"]["direct"] += 1
                PROG["latency"]["direct"] += tr["latency_s"]
                LAT["direct"].append(tr["latency_s"])
                PROG["median"]["direct"] = statistics.median(LAT["direct"])
                PROG["by_db"][db]["direct_done"] += 1
                PROG["by_diff"][r["difficulty"]]["direct_done"] += 1
                bump(q, "direct", ok)
        else:
            s1, s2 = tr["stage1"], tr["stage2"]
            failed = bool(s1.get("error") or s2.get("error"))
            s_ok, s_cls, s_err = score(q, viewcon(db), s1["dummy_sql"])
            ok, cls, err = score(q, phys(db), r["final_sql"])
            RES[q].update(stage1_ok=s_ok, stage1_class=s_cls, stage1_error=s_err, vsql_ok=ok, vsql_class=cls, vsql_error=err, dummy_sql=s1["dummy_sql"], vsql_sql=r["final_sql"], view_leak=s2["view_leak"], dummy_joins=s1["joins"], final_joins=s2["joins"], vsql_latency_s=s1["latency_s"] + s2["latency_s"])
            with LOCK:
                PROG["done"]["vsql"] += 1
                PROG["latency"]["vsql"] += s1["latency_s"] + s2["latency_s"]
                LAT["vsql"].append(s1["latency_s"] + s2["latency_s"])
                PROG["median"]["vsql"] = statistics.median(LAT["vsql"])
                PROG["by_db"][db]["vsql_done"] += 1
                PROG["by_diff"][r["difficulty"]]["vsql_done"] += 1
                bump(q, "stage1", s_ok)
                bump(q, "vsql", ok)
        consec = consec + 1 if failed else 0
        with LOCK:
            PROG["llm_errors"] += failed
            PROG["current"] = f"Q{q} · {db}"
    return consec


_profile = model_registry.get_profile(MODEL)
env = dict(
    os.environ,
    LLM_BASE_URL=_profile.base_url,
    LLM_API_KEY=_profile.api_key,
    SELECTED_MODEL=MODEL,
    LLM_TOKEN_PARAM=_profile.token_param,
    LLM_REASONING_EFFORT=_profile.extra.get("reasoning_effort", ""),
    PYTHONUNBUFFERED="1",
)
aborted = None
seen = {"direct": 0, "vsql": 0}
for method in ("direct", "vsql"):
    mdir = f"{OUT}/{method}"
    os.makedirs(mdir, exist_ok=True)
    trace = f"{mdir}/trace.jsonl"
    with LOCK:
        PROG["phase"] = method
    with open(f"{mdir}/run.log", "a", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "run_experiment.py", "--method", method, "--view-mode", ARGS.view_mode, "--data", SAMPLE, "--output-dir", mdir, "--no-eval", "--schema-mode", ARGS.schema_mode], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        consec = 0
        while True:
            running = proc.poll() is None
            consec = consume(method, trace, seen, consec)
            if consec >= MAX_CONSEC_ERR:
                proc.terminate()
                aborted = f"{method}: {consec} LLM errors in a row"
                break
            if SPENT["usd"] > ARGS.budget:
                proc.terminate()
                aborted = f"{method}: budget ${ARGS.budget} reached (${SPENT['usd']:.3f})"
                break
            if not running:
                break
            time.sleep(1.5)
        proc.wait()
    if proc.returncode and not aborted:
        aborted = f"{method}: run_experiment exit {proc.returncode}"
    if aborted:
        break


def ex(rows, key):
    xs = [r[key] for r in rows if key in r]
    return {"correct": sum(xs), "n": len(xs), "ex": round(sum(xs) / len(xs) * 100, 2) if xs else 0.0}


def mcnemar(rows, a, b):
    pairs = [(a(r), b(r)) for r in rows]
    x, y = sum(p and not q for p, q in pairs), sum(q and not p for p, q in pairs)
    n = x + y
    return {"a_only": x, "b_only": y, "exact_p": min(1.0, 2 * sum(math.comb(n, k) for k in range(min(x, y) + 1)) / 2 ** n) if n else 1.0}


rows = sorted(RES.values(), key=lambda r: r["question_id"])
_schemas = {db: load_db_schema(db) for db in VIEWS}
for r in rows:
    b = BASE[r["question_id"]]
    r.update(base7b_direct_ok=b["direct_ok"], base7b_stage1_ok=b["stage1_ok"], base7b_vsql_ok=b["vsql_ok"], coverage_gap=b["coverage_gap"], gold_joins=b["gold_joins"])
    r["view_gaps"] = gold_gaps(QS[r["question_id"]]["SQL"], VIEWS[r["db_id"]], _schemas[r["db_id"]])
with open(f"{OUT}/per_question.jsonl", "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

complete = [r for r in rows if "direct_ok" in r and "vsql_ok" in r]
summary = {
    "model": MODEL, "view_mode": ARGS.view_mode, "schema_mode": ARGS.schema_mode, "aborted": aborted, "n_complete": len(complete),
    "reused_traces": REUSED, "new_spend": {**SPENT, "usd": round(SPENT["usd"], 4)},
    "view_gap": {g: {k: ex([r for r in complete if bool(r["view_gaps"]) == v], k + "_ok") for k in SER} for g, v in (("gap", True), ("no_gap", False))},
    "this_model": {k: ex(complete, k + "_ok") for k in SER},
    "base_7b_same_questions": {k: ex(complete, f"base7b_{k}_ok") for k in SER},
    "by_difficulty": {d: {k: ex([r for r in complete if r["difficulty"] == d], k + "_ok") for k in SER} for d in by_diff_n},
    "by_db": {d: {k: ex([r for r in complete if r["db_id"] == d], k + "_ok")["correct"] for k in SER} | {"n": sum(r["db_id"] == d for r in complete)} for d in sorted(by_db_n)},
    "direct_vs_vsql_this_model": mcnemar(complete, lambda r: r["direct_ok"], lambda r: r["vsql_ok"]),
    "direct_7b_vs_this_model": mcnemar(complete, lambda r: r["base7b_direct_ok"], lambda r: r["direct_ok"]),
    "vsql_7b_vs_this_model": mcnemar(complete, lambda r: r["base7b_vsql_ok"], lambda r: r["vsql_ok"]),
    "direct_only_breakdown": {"stage1_wrong": sum(r["direct_ok"] and not r["vsql_ok"] and not r["stage1_ok"] for r in complete), "stage1_right_stage2_broke": sum(r["direct_ok"] and not r["vsql_ok"] and r["stage1_ok"] for r in complete)},
    "stage_transitions": dict(collections.Counter(("S1ok" if r["stage1_ok"] else "S1bad") + "->" + ("FINok" if r["vsql_ok"] else "FINbad") for r in complete)),
    "classes": {k: dict(collections.Counter(r[k + "_class"] for r in complete).most_common()) for k in SER},
    "coverage": {g: {k: ex([r for r in complete if r["coverage_gap"] == v], k + "_ok") for k in SER} for g, v in (("gap", True), ("no_gap", False))},
    "view_leak": sum(r.get("view_leak", False) for r in complete),
    "avg_latency_s": {"direct": round(sum(r["direct_latency_s"] for r in complete) / max(1, len(complete)), 1), "vsql": round(sum(r["vsql_latency_s"] for r in complete) / max(1, len(complete)), 1)},
    "llm_errors": PROG["llm_errors"], "elapsed_s": round(time.time() - start),
}
with open(f"{OUT}/metrics.json", "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False, indent=1))
with LOCK:
    PROG["status"] = "error" if aborted else "done"
    PROG["message"] = aborted or ""
    PROG["current"] = None
time.sleep(6)
sys.exit(1 if aborted else 0)
