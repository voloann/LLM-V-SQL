"""Builds the extended view sets used to test how much view coverage matters for V-SQL.

views/fk:   manual views with every column of their source tables, plus one view per uncovered table
            joined to its foreign-key parents. Never reads gold SQL, though the manual base views were
            written from gold joins.
views/gold: manual views plus exactly what the benchmark's gold SQL needs: missing columns and one view
            per gold join combination no manual view covers. This reads the test answers, like the paper's
            hand-built views, so its score is optimistic. It is not a strict ceiling: its INNER JOIN views
            can drop rows that a question needs.

Usage: python build_views.py
"""
import collections
import json
import os
import re
import sqlite3
import time

import sqlglot
from sqlglot import exp

import config
from schema_describe import view_column_sources
from sql_utils import parse_views_from_sql

RESERVED = {"order", "group", "index", "table", "select", "from", "where", "join", "transaction", "values", "default", "check", "to"}
ROW_COUNT_TIMEOUT_S = 5.0
# The paper bases views on frequently used joins and warns against one view per join in gold SQL.
# This threshold was fixed before the paper mode was run and must not be tuned on its results.
PAPER_MIN_QUESTIONS = 3


def load_db_schema(db_id: str) -> dict:
    """Returns {"tables": {real_name: {"columns", "pk", "fks"}}, "lookup": {lower_name: real_name}}."""
    con = sqlite3.connect(f"file:{config.DB_ROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        tables = {}
        for name in names:
            info = con.execute(f'PRAGMA table_info("{name}")').fetchall()
            fks = con.execute(f'PRAGMA foreign_key_list("{name}")').fetchall()
            tables[name] = {
                "columns": [c[1] for c in info],
                "pk": [c[1] for c in sorted(info, key=lambda c: c[5]) if c[5]],
                "fks": [{"table": f[2], "from": f[3], "to": f[4]} for f in fks],
            }
    finally:
        con.close()
    return {"tables": tables, "lookup": {name.lower(): name for name in tables}}


def load_manual_views(db_id: str) -> list[dict]:
    with open(os.path.join(config.VIEWS_DIR, "manual", f"{db_id}.json"), encoding="utf-8") as f:
        return json.load(f)["views"]


def _identifier(name: str) -> exp.Identifier:
    return exp.to_identifier(name, quoted=not re.fullmatch(r"[A-Za-z_]\w*", name) or name.lower() in RESERVED)


def _quote(name: str) -> str:
    return _identifier(name).sql(dialect="sqlite")


def _unique_name(column: str, table_alias: str, taken: set[str]) -> str:
    candidate, suffix = column, 2
    if candidate.lower() in taken:
        candidate = f"{table_alias}_{column}"
    while candidate.lower() in taken:
        candidate, suffix = f"{table_alias}_{column}_{suffix}", suffix + 1
    taken.add(candidate.lower())
    return candidate


def _build_view(sql: str) -> dict:
    view = parse_views_from_sql(sql)[0]
    view.update(valid=True, row_count=None, error=None)
    return view


def _extend_view(view: dict, wanted: dict[str, list[str]]) -> dict:
    """Adds the wanted columns ({table_lower: [columns]}) to a view without changing its joins."""
    tree = sqlglot.parse_one(re.sub(r"/\*.*?\*/", "", view["create_sql"], flags=re.S), read="sqlite")
    select = tree.expression
    aliases = [(t.alias or t.name, t.name) for t in select.find_all(exp.Table)]
    taken = {name.lower() for name in select.named_selects}
    exposed = set()
    for projection in select.selects:
        columns = list(projection.find_all(exp.Column))
        if len(columns) == 1:
            exposed.add(((columns[0].table or aliases[0][0]).lower(), columns[0].name.lower()))
    additions = []
    for alias, table in aliases:
        for column in wanted.get(table.lower(), []):
            if (alias.lower(), column.lower()) in exposed:
                continue
            name = _unique_name(column, alias, taken)
            reference = exp.Column(this=_identifier(column), table=_identifier(alias))
            additions.append(reference if name == column else exp.alias_(reference, _identifier(name)))
    if additions:
        select.select(*additions, copy=False)
    return _build_view(tree.sql(dialect="sqlite"))


def _instance_aliases(tables: list[str]) -> list[str]:
    seen = collections.Counter()
    aliases = []
    for table in tables:
        seen[table.lower()] += 1
        aliases.append(table if seen[table.lower()] == 1 else f"{table}_{seen[table.lower()]}")
    return aliases


def _render_select(instances: list[str], joins: list[tuple], columns_for, join_kind: str) -> str:
    """instances[0] is the FROM table; joins are (instance, on_left_instance, left_col, right_col)."""
    aliases = _instance_aliases(instances)
    taken, projections = set(), []
    for alias, table in zip(aliases, instances):
        for column in columns_for(table):
            name = _unique_name(column, alias, taken)
            reference = f"{_quote(alias)}.{_quote(column)}"
            projections.append(reference if name == column else f"{reference} AS {_quote(name)}")

    def source(i):
        return _quote(instances[i]) if aliases[i] == instances[i] else f"{_quote(instances[i])} AS {_quote(aliases[i])}"

    parts = [f"SELECT {', '.join(projections)} FROM {source(0)}"]
    for right, left, left_col, right_col in joins:
        parts.append(f"{join_kind} JOIN {source(right)} ON {_quote(aliases[left])}.{_quote(left_col)} = {_quote(aliases[right])}.{_quote(right_col)}")
    return " ".join(parts)


def build_fk_views(db_id):
    schema = load_db_schema(db_id)
    tables = schema["tables"]
    all_columns = {name.lower(): info["columns"] for name, info in tables.items()}
    manual = load_manual_views(db_id)
    views = [_extend_view(view, all_columns) for view in manual]
    covered = {t.lower() for view in manual for t in view["source_tables"]}
    for name, info in tables.items():
        if name.lower() in covered:
            continue
        instances, joins = [name], []
        for fk in info["fks"]:
            parent = schema["lookup"].get(fk["table"].lower())
            if not parent:
                continue
            target = fk["to"] or (tables[parent]["pk"][0] if tables[parent]["pk"] else None)
            if not target:
                continue
            instances.append(parent)
            joins.append((len(instances) - 1, 0, fk["from"], target))
        body = _render_select(instances, joins, lambda t: tables[t]["columns"], "LEFT")
        views.append(_build_view(f"CREATE VIEW {_quote('v_' + name.lower())} AS {body}"))
    return views


def gold_usage(sql: str, schema: dict) -> dict:
    """Physical tables, columns and join edges a query needs. All names are lower case.

    selects: one entry per SELECT, with instances (sorted table names, repeated for self joins) and
    edges (left_index, left_col, right_index, right_col) into instances.
    """
    tree = sqlglot.parse_one(sql, read="sqlite")
    lookup = schema["lookup"]
    columns_of = {name.lower(): {c.lower() for c in info["columns"]} for name, info in schema["tables"].items()}

    scopes = {}
    for select in tree.find_all(exp.Select):
        sources = [t for t in select.find_all(exp.Table) if t.find_ancestor(exp.Select) is select and t.name.lower() in lookup]
        sources.sort(key=lambda t: t.name.lower())
        scopes[id(select)] = {
            "select": select,
            "instances": [t.name.lower() for t in sources],
            "aliases": {(t.alias or t.name).lower(): i for i, t in enumerate(sources)},
            "edges": [],
        }

    def chain(node):
        select = node.find_ancestor(exp.Select)
        while select is not None:
            yield scopes[id(select)]
            select = select.find_ancestor(exp.Select)

    def resolve(column):
        name = column.name.lower()
        qualifier = column.table.lower() if column.table else None
        for scope in chain(column):
            if qualifier:
                if qualifier in scope["aliases"]:
                    index = scope["aliases"][qualifier]
                    return (scope, index) if name in columns_of[scope["instances"][index]] else None
            else:
                for index, table in enumerate(scope["instances"]):
                    if name in columns_of[table]:
                        return scope, index
        return None

    columns = set()
    for column in tree.find_all(exp.Column):
        found = resolve(column)
        if found:
            columns.add((found[0]["instances"][found[1]], column.name.lower()))

    for equality in tree.find_all(exp.EQ):
        if isinstance(equality.left, exp.Column) and isinstance(equality.right, exp.Column):
            left, right = resolve(equality.left), resolve(equality.right)
            if left and right and left[0] is right[0] and left[1] != right[1]:
                left[0]["edges"].append((left[1], equality.left.name.lower(), right[1], equality.right.name.lower()))

    selects = [{"instances": s["instances"], "edges": s["edges"]} for s in scopes.values() if s["instances"]]
    return {"tables": {t for s in selects for t in s["instances"]} | {t for t, _ in columns}, "columns": columns, "selects": selects}


def _components(select: dict) -> list[dict]:
    """Splits one SELECT's tables into groups linked by join edges."""
    parent = list(range(len(select["instances"])))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for left, _, right, _ in select["edges"]:
        parent[find(left)] = find(right)
    groups = collections.defaultdict(list)
    for i in range(len(parent)):
        groups[find(i)].append(i)
    result = []
    for members in groups.values():
        position = {old: new for new, old in enumerate(members)}
        result.append(
            {
                "instances": [select["instances"][i] for i in members],
                "edges": [(position[a], ca, position[b], cb) for a, ca, b, cb in select["edges"] if a in position and b in position],
            }
        )
    return result


def _view_instances(view: dict) -> collections.Counter:
    tree = sqlglot.parse_one(re.sub(r"/\*.*?\*/", "", view["create_sql"], flags=re.S), read="sqlite")
    return collections.Counter(t.name.lower() for t in tree.expression.find_all(exp.Table))


def _contained(instances: list[str], view_instances: list[collections.Counter]) -> bool:
    need = collections.Counter(instances)
    return any(not (need - have) for have in view_instances)


def gold_gaps(sql: str, views: list[dict], schema: dict) -> list[str]:
    """What a query needs that the views do not offer: tables, columns, or a join no single view holds."""
    usage = gold_usage(sql, schema)
    exposed = set()
    instances = []
    for view in views:
        exposed |= {source for source in view_column_sources(view).values() if source}
        instances.append(_view_instances(view))
    covered_tables = {t for have in instances for t in have}
    gaps = [f"table:{t}" for t in sorted(usage["tables"] - covered_tables)]
    gaps += [f"column:{t}.{c}" for t, c in sorted(usage["columns"]) if t in covered_tables and (t, c) not in exposed]
    for select in usage["selects"]:
        for component in _components(select):
            if len(component["instances"]) > 1 and not _contained(component["instances"], instances):
                gaps.append("join:" + "+".join(sorted(component["instances"])))
    return gaps


def _row_counts(db_id: str, tables) -> dict:
    con = sqlite3.connect(f"file:{config.DB_ROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
    try:
        return {table: con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    finally:
        con.close()


def build_gold_views(db_id: str, questions: list[dict], min_questions: int = 1, join_type: str = "INNER") -> list[dict]:
    """Manual views plus what gold SQL needs.

    min_questions drops table combinations used by fewer questions. With LEFT joins each view starts from its
    largest table, so that table keeps all its rows.
    """
    schema = load_db_schema(db_id)
    tables = schema["tables"]
    used = collections.defaultdict(set)
    components = {}
    question_counts = collections.Counter()
    for question in questions:
        usage = gold_usage(question["SQL"], schema)
        for table, column in usage["columns"]:
            used[table].add(column)
        keys = set()
        for select in usage["selects"]:
            for component in _components(select):
                key = tuple(sorted(component["instances"]))
                components.setdefault(key, component)
                keys.add(key)
        question_counts.update(keys)
    rows = _row_counts(db_id, tables) if join_type == "LEFT" else {}

    def real_columns(table):
        return [c for c in tables[schema["lookup"][table.lower()]]["columns"] if c.lower() in used[table.lower()]]

    manual = load_manual_views(db_id)
    views = [_extend_view(view, {t: real_columns(t) for t in used}) for view in manual]
    manual_instances = [_view_instances(view) for view in manual]
    taken = {view["name"].lower() for view in views}

    for key, component in sorted(components.items()):
        if _contained(list(key), manual_instances) or question_counts[key] < min_questions:
            continue
        real = [schema["lookup"][t] for t in component["instances"]]
        start = max(range(len(real)), key=lambda i: rows[real[i]]) if join_type == "LEFT" else 0
        joins, reached, pending = [], {start}, list(component["edges"])
        while pending and len(reached) < len(real):
            progressed = False
            for edge in list(pending):
                left, left_col, right, right_col = edge
                if left in reached and right in reached:
                    pending.remove(edge)
                    continue
                if left not in reached and right not in reached:
                    continue
                if right in reached:
                    left, left_col, right, right_col = right, right_col, left, left_col
                reached.add(right)
                joins.append((right, left, left_col, right_col))
                pending.remove(edge)
                progressed = True
            if not progressed:
                break
        keys = collections.defaultdict(set)
        for a, ca, b, cb in component["edges"]:
            keys[component["instances"][a]].add(ca)
            keys[component["instances"][b]].add(cb)

        def columns_for(table):
            lower = table.lower()
            wanted = used[lower] | keys[lower]
            return [c for c in tables[table]["columns"] if c.lower() in wanted] or tables[table]["columns"][:1]

        # Join order must follow the spanning order, with instances renumbered so FROM comes first.
        order = [start] + [right for right, _, _, _ in joins]
        position = {old: new for new, old in enumerate(order)}
        ordered = [real[i] for i in order]
        ordered_joins = [(position[r], position[l], lc, rc) for r, l, lc, rc in joins]
        body = _render_select(ordered, ordered_joins, columns_for, join_type)
        base = "v_" + "_".join(sorted({t.lower() for t in key}))[:48] if len(key) > 1 else f"v_{key[0]}"
        name, suffix = base, 2
        while name in taken:
            name, suffix = f"{base}_{suffix}", suffix + 1
        taken.add(name)
        views.append(_build_view(f"CREATE VIEW {_quote(name)} AS {body}"))
    return views


def _validate(db_id: str, views: list[dict]) -> None:
    con = sqlite3.connect(f"file:{config.DB_ROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
    try:
        for view in views:
            try:
                con.execute(re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", view["create_sql"], flags=re.I))
                deadline = time.time() + ROW_COUNT_TIMEOUT_S
                con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 100000)
                try:
                    view["row_count"] = con.execute(f'SELECT COUNT(*) FROM "{view["name"]}"').fetchone()[0]
                except sqlite3.OperationalError:
                    view["row_count"] = None
                finally:
                    con.set_progress_handler(None, 0)
            except Exception as exc:
                view.update(valid=False, error=str(exc))
    finally:
        con.close()


def write_views(mode: str, db_id: str, views: list[dict]) -> None:
    _validate(db_id, views)
    out_dir = os.path.join(config.VIEWS_DIR, mode)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{db_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"db_id": db_id, "mode": mode, "db_untouched": True, "views": views}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, f"{db_id}.sql"), "w", encoding="utf-8") as f:
        f.write(";\n\n".join(view["create_sql"] for view in views) + ";\n")


def main():
    with open(config.DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    by_db = collections.defaultdict(list)
    for question in questions:
        by_db[question["db_id"]].append(question)

    report = {}
    for db_id in sorted(by_db):
        schema = load_db_schema(db_id)
        total_columns = sum(len(info["columns"]) for info in schema["tables"].values())
        row = {"tables": len(schema["tables"]), "columns": total_columns, "questions": len(by_db[db_id])}
        view_sets = (
            ("manual", load_manual_views(db_id)),
            ("fk", build_fk_views(db_id)),
            ("gold", build_gold_views(db_id, by_db[db_id])),
            ("paper", build_gold_views(db_id, by_db[db_id], min_questions=PAPER_MIN_QUESTIONS, join_type="LEFT")),
        )
        for mode, views in view_sets:
            if mode != "manual":
                write_views(mode, db_id, views)
            exposed = {source for view in views for source in view_column_sources(view).values() if source}
            with_gap = sum(bool(gold_gaps(q["SQL"], views, schema)) for q in by_db[db_id])
            row[mode] = {
                "views": len(views),
                "view_columns": sum(len(view["columns"]) for view in views),
                "distinct_columns_exposed": len(exposed),
                "questions_with_gap": with_gap,
                "invalid_views": [view["name"] for view in views if view.get("valid") is False],
            }
        report[db_id] = row
        print(db_id, json.dumps(row, ensure_ascii=False), flush=True)

    totals = {
        mode: {
            key: sum(report[db][mode][key] for db in report)
            for key in ("views", "view_columns", "distinct_columns_exposed", "questions_with_gap")
        }
        for mode in ("manual", "fk", "gold", "paper")
    }
    with open(os.path.join(config.VIEWS_DIR, "coverage_report.json"), "w", encoding="utf-8") as f:
        json.dump({"totals": totals, "by_db": report}, f, indent=2, ensure_ascii=False)
    print(json.dumps(totals, indent=1))


if __name__ == "__main__":
    main()
