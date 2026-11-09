"""Re-score stored predictions on physical tables only (no views), no LLM needed.

usage: rescore.py <project_root> <output_dir>
Databases are opened read-only; a DB that holds views is copied to memory and the views dropped there.
Scoring matches evaluation_ex.calculate_ex: set(pred rows) == set(gold rows), 30s limit per prediction.
"""
import collections, http.server, json, math, os, re, sqlite3, sys, threading, time
import sqlglot
from sqlglot import exp

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
TIMEOUT = 30.0
ROW_CAP = 2_000_000


def load_trace(run):
    with open(f"{ROOT}/outputs/{run}/trace.jsonl", encoding="utf-8") as f:
        return {r["question_id"]: r for r in (json.loads(l) for l in f if l.strip())}


D, V = load_trace("500_all_direct"), load_trace("500_all_vsql")
VIEWS = {}
for fn in os.listdir(f"{ROOT}/views/manual"):
    if fn.endswith(".json"):
        with open(f"{ROOT}/views/manual/{fn}", encoding="utf-8") as f:
            VIEWS[fn[:-5]] = json.load(f)["views"]


def parse(sql):
    try:
        return sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return None


def execute(con, sql, limit=TIMEOUT):
    """Returns (rowset, width, error). Error 'timeout' means the 30s limit fired."""
    deadline = time.time() + limit
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 200000)
    try:
        cur = con.execute(sql)
        width = len(cur.description or [])
        rows = set()
        n = 0
        while True:
            chunk = cur.fetchmany(20000)
            if not chunk:
                break
            rows.update(chunk)
            n += len(chunk)
            if n > ROW_CAP:
                return None, width, "too_many_rows"
        return rows, width, None
    except sqlite3.OperationalError as e:
        return (None, 0, "timeout") if "interrupt" in str(e).lower() else (None, 0, str(e))
    except Exception as e:
        return None, 0, str(e)
    finally:
        con.set_progress_handler(None, 0)


def open_physical(db_id):
    path = f"{ROOT}/mini_dev_databases/{db_id}/{db_id}.sqlite"
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    views = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='view'")]
    if not views:
        return src, []
    mem = sqlite3.connect(":memory:")
    src.backup(mem)
    src.close()
    for v in views:
        mem.execute(f'DROP VIEW "{v}"')
    return mem, views


def open_views(db_id):
    path = f"{ROOT}/mini_dev_databases/{db_id}/{db_id}.sqlite"
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    failed = []
    for v in VIEWS[db_id]:
        ddl = re.sub(r"/\*.*?\*/", "", v["create_sql"], flags=re.S).strip()
        try:
            con.execute(re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", ddl, flags=re.I))
        except Exception as e:
            failed.append((v["name"], str(e)))
    return con, failed


def classify(ok, err, width, gold_width):
    if ok:
        return "correct"
    if err == "timeout":
        return "timeout"
    if err == "too_many_rows":
        return "too_many_rows"
    if err:
        m = re.match(r"no such (column|table|function)", err)
        if m:
            return "no such " + m.group(1)
        return "syntax" if ("syntax" in err or "incomplete" in err) else "other_error"
    return "wrong_column_count" if width != gold_width else "wrong_values"


names = {}
for db, vs in VIEWS.items():
    s = set()
    for v in vs:
        s |= {c.lower() for c in v["columns"]}
        t = parse(v["create_sql"])
        if t is not None and t.expression is not None:
            s |= {c.name.lower() for c in t.expression.find_all(exp.Column)}
    names[db] = s


def has_gap(r):
    t = parse(r["gold_sql"])
    al = {a.alias.lower() for a in t.find_all(exp.Alias)}
    return any(c.find_ancestor(exp.Join) is None and c.name.lower() not in names[r["db_id"]] and c.name.lower() not in al for c in t.find_all(exp.Column))


rows = []
meta = {"persisted_views": {}, "view_create_failures": {}, "gold_errors": [], "gold_slow": []}
by_db = collections.defaultdict(list)
for q, r in V.items():
    by_db[r["db_id"]].append(q)

start = time.time()

# --- live progress page on http://127.0.0.1:8765 (read by the Browser pane) ---
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.html")
LOCK = threading.Lock()
blank = lambda n: {"n": n, "done": 0, "direct": 0, "stage1": 0, "vsql": 0}
diff_n = collections.Counter(r["difficulty"] for r in V.values())
PROG = {
    "status": "running", "total": len(V), "done": 0, "elapsed": 0, "current": None, "timeouts": 0,
    "ok": {"direct": 0, "stage1": 0, "vsql": 0},
    "by_db": {d: blank(len(by_db[d])) for d in sorted(by_db)},
    "by_diff": {d: blank(diff_n[d]) for d in ("simple", "moderate", "challenging")},
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/progress"):
            with LOCK:
                PROG["elapsed"] = round(time.time() - start, 1)
                body, ctype = json.dumps(PROG).encode(), "application/json"
        elif self.path == "/":
            with open(PAGE, "rb") as fh:
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


threading.Thread(target=http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever, daemon=True).start()
print("progress page: http://127.0.0.1:8765", flush=True)

for db_id in sorted(by_db):
    t0 = time.time()
    with LOCK:
        PROG["current"] = db_id
    phys, persisted = open_physical(db_id)
    vcon, failed = open_views(db_id)
    if persisted:
        meta["persisted_views"][db_id] = persisted
    if failed:
        meta["view_create_failures"][db_id] = failed
    for q in by_db[db_id]:
        r = V[q]
        g, gw, ge = execute(phys, r["gold_sql"], limit=300.0)
        if ge:
            meta["gold_errors"].append({"q": q, "err": ge})
        d, dw, de = execute(phys, D[q]["final_sql"])
        f, fw, fe = execute(phys, r["final_sql"])
        s, sw, se = execute(vcon, r["trace"]["stage1"]["dummy_sql"])
        d_ok, f_ok, s_ok = (d == g and not ge), (f == g and not ge), (s == g and not ge)
        rows.append({
            "question_id": q, "db_id": db_id, "difficulty": r["difficulty"],
            "direct_ok": d_ok, "stage1_ok": s_ok, "vsql_ok": f_ok,
            "direct_class": classify(d_ok, de, dw, gw), "stage1_class": classify(s_ok, se, sw, gw), "vsql_class": classify(f_ok, fe, fw, gw),
            "direct_error": de, "stage1_error": se, "vsql_error": fe,
            "view_leak": r["trace"]["stage2"]["view_leak"], "coverage_gap": has_gap(r),
            "gold_joins": r["gold_joins"], "direct_joins": D[q]["trace"]["joins"], "dummy_joins": r["trace"]["stage1"]["joins"], "final_joins": r["trace"]["stage2"]["joins"],
        })
        with LOCK:
            PROG["done"] += 1
            PROG["timeouts"] += sum(e == "timeout" for e in (de, fe, se))
            for key, ok in (("direct", d_ok), ("stage1", s_ok), ("vsql", f_ok)):
                PROG["ok"][key] += ok
                PROG["by_db"][db_id][key] += ok
                PROG["by_diff"][r["difficulty"]][key] += ok
            PROG["by_db"][db_id]["done"] += 1
            PROG["by_diff"][r["difficulty"]]["done"] += 1
    phys.close()
    vcon.close()
    print(f"[{db_id}] {len(by_db[db_id])} q in {time.time()-t0:.0f}s", flush=True)

with open(f"{OUT}/per_question.jsonl", "w", encoding="utf-8") as fh:
    for x in sorted(rows, key=lambda z: z["question_id"]):
        fh.write(json.dumps(x, ensure_ascii=False) + "\n")


def pct(a, b):
    return round(a / b * 100, 2) if b else 0.0


def ex(subset, key):
    return {"correct": sum(x[key] for x in subset), "n": len(subset), "ex": pct(sum(x[key] for x in subset), len(subset))}


b = sum(x["direct_ok"] and not x["vsql_ok"] for x in rows)
c = sum(x["vsql_ok"] and not x["direct_ok"] for x in rows)
n = b + c
pval = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0
summary = {
    "meta": meta,
    "total": {k: ex(rows, k) for k in ("direct_ok", "stage1_ok", "vsql_ok")},
    "by_difficulty": {d: {k: ex([x for x in rows if x["difficulty"] == d], k) for k in ("direct_ok", "stage1_ok", "vsql_ok")} for d in ("simple", "moderate", "challenging")},
    "by_db": {d: {**{k: ex([x for x in rows if x["db_id"] == d], k)["correct"] for k in ("direct_ok", "stage1_ok", "vsql_ok")}, "n": len(by_db[d]), "coverage_gap": sum(x["coverage_gap"] for x in rows if x["db_id"] == d), "leak": sum(x["view_leak"] for x in rows if x["db_id"] == d)} for d in sorted(by_db)},
    "direct_vs_vsql": {"direct_only": b, "vsql_only": c, "both": sum(x["direct_ok"] and x["vsql_ok"] for x in rows), "neither": sum(not x["direct_ok"] and not x["vsql_ok"] for x in rows), "mcnemar_exact_p": pval},
    "direct_only_breakdown": {"stage1_already_wrong": sum(x["direct_ok"] and not x["vsql_ok"] and not x["stage1_ok"] for x in rows), "stage1_right_stage2_broke": sum(x["direct_ok"] and not x["vsql_ok"] and x["stage1_ok"] for x in rows)},
    "stage_transitions": dict(collections.Counter(("S1ok" if x["stage1_ok"] else "S1bad") + "->" + ("FINok" if x["vsql_ok"] else "FINbad") for x in rows)),
    "classes": {k: dict(collections.Counter(x[k + "_class"] for x in rows).most_common()) for k in ("direct", "stage1", "vsql")},
    "coverage": {
        "gap_questions": sum(x["coverage_gap"] for x in rows),
        "gap": {k: ex([x for x in rows if x["coverage_gap"]], k) for k in ("direct_ok", "stage1_ok", "vsql_ok")},
        "no_gap": {k: ex([x for x in rows if not x["coverage_gap"]], k) for k in ("direct_ok", "stage1_ok", "vsql_ok")},
    },
    "joins_vs_gold": {
        "direct": {"fewer": sum(x["direct_joins"] < x["gold_joins"] for x in rows), "equal": sum(x["direct_joins"] == x["gold_joins"] for x in rows), "more": sum(x["direct_joins"] > x["gold_joins"] for x in rows)},
        "final": {"fewer": sum(x["final_joins"] < x["gold_joins"] for x in rows), "equal": sum(x["final_joins"] == x["gold_joins"] for x in rows), "more": sum(x["final_joins"] > x["gold_joins"] for x in rows)},
        "ex_when_final_fewer": ex([x for x in rows if x["final_joins"] < x["gold_joins"]], "vsql_ok"),
        "ex_when_final_equal": ex([x for x in rows if x["final_joins"] == x["gold_joins"]], "vsql_ok"),
        "no_such_column_fewer_joins": sum(x["vsql_class"] == "no such column" and x["final_joins"] < x["gold_joins"] for x in rows),
        "no_such_column_total": sum(x["vsql_class"] == "no such column" for x in rows),
    },
    "leak": {"flagged": sum(x["view_leak"] for x in rows), "classes": dict(collections.Counter(x["vsql_class"] for x in rows if x["view_leak"]))},
    "stored_metrics_for_comparison": {"direct_total": 47.4, "vsql_total": 33.6},
    "elapsed_s": round(time.time() - start),
}
with open(f"{OUT}/metrics.json", "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False, indent=1))
with LOCK:
    PROG["status"] = "done"
    PROG["current"] = None
time.sleep(6)  # let the page's last poll see the final state
