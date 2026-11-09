"""Read-only SQL execution and Execution Accuracy scoring, matching evaluation_ex.calculate_ex: set(pred) == set(gold)."""
import re
import sqlite3
import time
from dataclasses import dataclass, field

import config

PREDICTION_TIMEOUT_S = 30.0
GOLD_TIMEOUT_S = 300.0
ROW_CAP = 2_000_000
SAMPLE_ROWS = 20


@dataclass
class QueryResult:
    rows: set | None = None
    columns: list = field(default_factory=list)
    sample: list = field(default_factory=list)
    total_rows: int = 0
    error: str | None = None
    seconds: float = 0.0

    def public(self) -> dict:
        """JSON-safe form for the browser."""
        return {
            "columns": self.columns,
            "rows": [[_json_value(v) for v in row] for row in self.sample],
            "total_rows": self.total_rows,
            "distinct_rows": len(self.rows) if self.rows is not None else 0,
            "error": self.error,
            "seconds": round(self.seconds, 3),
        }


def _json_value(value):
    return value.hex() if isinstance(value, (bytes, bytearray)) else value


def execute_query(con: sqlite3.Connection, sql: str, limit: float = PREDICTION_TIMEOUT_S) -> QueryResult:
    started = time.time()
    deadline = started + limit
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 200000)
    result = QueryResult()
    try:
        cursor = con.execute(sql)
        result.columns = [c[0] for c in cursor.description or []]
        rows = set()
        while True:
            chunk = cursor.fetchmany(20000)
            if not chunk:
                break
            if len(result.sample) < SAMPLE_ROWS:
                result.sample.extend(chunk[: SAMPLE_ROWS - len(result.sample)])
            rows.update(chunk)
            result.total_rows += len(chunk)
            if result.total_rows > ROW_CAP:
                result.error = "too_many_rows"
                result.rows = None
                result.seconds = time.time() - started
                return result
        result.rows = rows
    except sqlite3.OperationalError as exc:
        result.error = "timeout" if "interrupt" in str(exc).lower() else str(exc)
    except Exception as exc:
        result.error = str(exc)
    finally:
        con.set_progress_handler(None, 0)
    result.seconds = time.time() - started
    return result


def classify(ok: bool, error: str | None, width: int, gold_width: int) -> str:
    if ok:
        return "correct"
    if error in ("timeout", "too_many_rows"):
        return error
    if error:
        match = re.match(r"no such (column|table|function)", error)
        if match:
            return "no such " + match.group(1)
        return "syntax" if ("syntax" in error or "incomplete" in error) else "other_error"
    return "wrong_column_count" if width != gold_width else "wrong_values"


class EvalContext:
    """Connections owned by one thread: physical tables, and temp views per view set."""

    def __init__(self):
        self._physical = {}
        self._views = {}
        self._gold = {}

    @staticmethod
    def _open(db_id: str) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{config.DB_ROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)

    def physical(self, db_id: str) -> sqlite3.Connection:
        if db_id not in self._physical:
            self._physical[db_id] = self._open(db_id)
        return self._physical[db_id]

    def views(self, db_id: str, view_mode: str, parsed_views: list[dict]) -> sqlite3.Connection:
        key = (db_id, view_mode)
        if key not in self._views:
            con = self._open(db_id)
            for view in parsed_views:
                ddl = re.sub(r"/\*.*?\*/", "", view["create_sql"], flags=re.S).strip()
                con.execute(re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", ddl, flags=re.I))
            self._views[key] = con
        return self._views[key]

    def gold(self, question: dict) -> QueryResult:
        qid = question["question_id"]
        if qid not in self._gold:
            self._gold[qid] = execute_query(self.physical(question["db_id"]), question["SQL"], GOLD_TIMEOUT_S)
        return self._gold[qid]

    def compare(self, question: dict, predicted: QueryResult) -> dict:
        gold = self.gold(question)
        ok = predicted.error is None and gold.error is None and predicted.rows == gold.rows
        pred_rows = predicted.rows if predicted.rows is not None else set()
        gold_rows = gold.rows if gold.rows is not None else set()
        return {
            "ok": ok,
            "class": classify(ok, predicted.error, len(predicted.columns), len(gold.columns)),
            "pred_rows": len(pred_rows),
            "gold_rows": len(gold_rows),
            "matching": len(pred_rows & gold_rows),
            "only_pred": len(pred_rows - gold_rows),
            "only_gold": len(gold_rows - pred_rows),
            "error": predicted.error,
            "gold_error": gold.error,
        }

    def score(self, question: dict, sql: str) -> dict:
        return self.compare(question, execute_query(self.physical(question["db_id"]), sql))

    def close(self) -> None:
        for con in list(self._physical.values()) + list(self._views.values()):
            con.close()
