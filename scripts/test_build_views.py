"""Tests for view extension modes (fk, gold). Run: python scripts/test_build_views.py"""
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config
from build_views import (
    PAPER_MIN_QUESTIONS,
    build_fk_views,
    build_gold_views,
    gold_gaps,
    gold_usage,
    load_db_schema,
    load_manual_views,
)
from schema_describe import view_column_sources

DBS = sorted(d for d in os.listdir(config.DB_ROOT) if os.path.isdir(os.path.join(config.DB_ROOT, d)))
with open(config.DATA_PATH, encoding="utf-8") as f:
    QUESTIONS = json.load(f)


def questions_for(db):
    return [q for q in QUESTIONS if q["db_id"] == db]


def assert_views_execute(db, views):
    con = sqlite3.connect(f"file:{config.DB_ROOT}/{db}/{db}.sqlite?mode=ro", uri=True)
    for view in views:
        ddl = re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", view["create_sql"], flags=re.I)
        con.execute(ddl)
        cursor = con.execute(f'SELECT * FROM "{view["name"]}" LIMIT 1')
        names = [c[0] for c in cursor.description]
        assert [n.lower() for n in names] == [c.lower() for c in view["columns"]], (view["name"], names, view["columns"])
        assert len({n.lower() for n in names}) == len(names), (view["name"], "duplicate column")
    con.close()


def test_gold_usage_resolves_aliases_columns_and_edges():
    schema = load_db_schema("toxicology")
    usage = gold_usage(
        "SELECT T1.element FROM atom AS T1 JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+'",
        schema,
    )
    assert usage["tables"] == {"atom", "molecule"}, usage["tables"]
    assert {("atom", "element"), ("atom", "molecule_id"), ("molecule", "molecule_id"), ("molecule", "label")} <= usage["columns"], usage["columns"]
    assert len(usage["selects"]) == 1
    assert usage["selects"][0]["instances"] == ["atom", "molecule"]
    assert usage["selects"][0]["edges"], usage["selects"][0]


def test_gold_usage_resolves_unqualified_columns_inside_subquery():
    schema = load_db_schema("toxicology")
    usage = gold_usage("SELECT label FROM molecule WHERE molecule_id IN (SELECT molecule_id FROM atom WHERE element = 'cl')", schema)
    assert {("molecule", "label"), ("atom", "element"), ("atom", "molecule_id")} <= usage["columns"], usage["columns"]


def test_manual_views_have_gaps_so_the_measure_can_detect_them():
    total = sum(1 for db in DBS for q in questions_for(db) if gold_gaps(q["SQL"], load_manual_views(db), load_db_schema(db)))
    assert total > 100, total


def test_fk_views_expose_every_table_and_column():
    for db in DBS:
        schema = load_db_schema(db)
        views = build_fk_views(db)
        exposed = set()
        for view in views:
            exposed |= {source for source in view_column_sources(view).values() if source}
        for table, info in schema["tables"].items():
            for column in info["columns"]:
                assert (table.lower(), column.lower()) in exposed, (db, table, column)


def test_fk_build_does_not_read_gold_sql():
    original = build_fk_views.__code__.co_varnames[: build_fk_views.__code__.co_argcount]
    assert original == ("db_id",), original


def test_fk_views_execute_with_unique_columns():
    for db in DBS:
        assert_views_execute(db, build_fk_views(db))


def test_fk_extension_keeps_manual_view_rows():
    for db in ("financial", "superhero"):
        con = sqlite3.connect(f"file:{config.DB_ROOT}/{db}/{db}.sqlite?mode=ro", uri=True)
        manual = {v["name"]: v for v in load_manual_views(db)}
        for view in build_fk_views(db):
            if view["name"] in manual:
                old = con.execute("SELECT COUNT(*) FROM (" + re.sub(r"^.*?\bAS\s+SELECT", "SELECT", re.sub(r"/\*.*?\*/", "", manual[view["name"]]["create_sql"], flags=re.S), count=1, flags=re.I | re.S) + ")").fetchone()[0]
                new = con.execute("SELECT COUNT(*) FROM (" + re.sub(r"^.*?\bAS\s+SELECT", "SELECT", view["create_sql"], count=1, flags=re.I | re.S) + ")").fetchone()[0]
                assert old == new, (db, view["name"], old, new)
        con.close()


def test_fk_column_with_spaces_is_quoted_and_runs():
    views = build_fk_views("california_schools")
    assert any(any(" " in column for column in view["columns"]) for view in views)
    assert_views_execute("california_schools", views)


def test_fk_self_reference_keeps_both_parent_instances():
    connected = next(v for v in build_fk_views("toxicology") if v["name"] == "v_connected")
    assert connected["create_sql"].lower().count("join atom") == 2, connected["create_sql"]


def test_gold_views_leave_no_gap_for_any_question():
    for db in DBS:
        schema = load_db_schema(db)
        views = build_gold_views(db, questions_for(db))
        assert_views_execute(db, views)
        for q in questions_for(db):
            gaps = gold_gaps(q["SQL"], views, schema)
            assert not gaps, (db, q["question_id"], gaps)


def test_gold_views_keep_manual_views():
    views = {v["name"] for v in build_gold_views("toxicology", questions_for("toxicology"))}
    assert {"v_atom_molecule", "v_bond_molecule"} <= views, views


def paper_views(db):
    return build_gold_views(db, questions_for(db), min_questions=PAPER_MIN_QUESTIONS, join_type="LEFT")


def test_paper_views_add_only_combinations_used_by_enough_questions():
    assert PAPER_MIN_QUESTIONS == 3
    assert sum(len(paper_views(db)) for db in DBS) == 43


def test_full_gold_build_is_unchanged_by_the_new_options():
    views = [v for db in DBS for v in build_gold_views(db, questions_for(db))]
    assert len(views) == 90, len(views)
    manual = {(db, v["name"]) for db in DBS for v in load_manual_views(db)}
    new = [v for db in DBS for v in build_gold_views(db, questions_for(db)) if (db, v["name"]) not in manual]
    assert sum(" LEFT JOIN " in v["create_sql"].upper() for v in new) == 0
    assert sum(" INNER JOIN " in v["create_sql"].upper() for v in new) == 54


def test_paper_views_use_left_join_and_execute():
    for db in DBS:
        views = paper_views(db)
        assert_views_execute(db, views)
        for view in views:
            assert " INNER JOIN " not in view["create_sql"].upper(), (db, view["name"])


def test_paper_views_keep_manual_views_and_their_rows():
    for db in DBS:
        names = {v["name"] for v in paper_views(db)}
        assert {v["name"] for v in load_manual_views(db)} <= names, db


def test_paper_views_keep_every_row_of_their_largest_table():
    for db in ("toxicology", "superhero", "card_games"):
        con = sqlite3.connect(f"file:{config.DB_ROOT}/{db}/{db}.sqlite?mode=ro", uri=True)
        manual = {v["name"] for v in load_manual_views(db)}
        for view in paper_views(db):
            if view["name"] in manual:
                continue
            con.execute(re.sub(r"^CREATE\s+VIEW", "CREATE TEMP VIEW", view["create_sql"], flags=re.I))
            rows = con.execute(f'SELECT COUNT(*) FROM "{view["name"]}"').fetchone()[0]
            largest = max(con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in view["source_tables"])
            assert rows >= largest, (db, view["name"], rows, largest)
        con.close()


def test_load_db_configs_reads_new_modes_and_leaves_direct_schema_alone():
    from run_experiment import load_db_configs

    manual = load_db_configs(view_mode="manual", schema_mode="described")
    extended = load_db_configs(view_mode="fk", schema_mode="described")
    assert manual["toxicology"]["direct_schema"] == extended["toxicology"]["direct_schema"]
    assert "v_connected" in extended["toxicology"]["view_schema"]


def test_described_schema_quotes_names_with_spaces():
    from run_experiment import load_db_configs

    schema = load_db_configs(view_mode="fk", schema_mode="described")["california_schools"]["view_schema"]
    assert '"Free Meal Count (Ages 5-17)"' in schema, schema[:400]


def test_stage2_table_filter_keeps_every_linked_table():
    import v_sql_pipeline_LLM as pipeline
    from run_experiment import load_db_configs

    configs = load_db_configs(view_mode="fk", schema_mode="described")
    for db, cfg in configs.items():
        for view in cfg["parsed_views"]:
            _, tables, _ = pipeline.filter_stage2_schema(f"SELECT 1 FROM {view['name']}", cfg)
            found = {m.lower() for m in re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"'\[]?(\w+)", tables, flags=re.I)}
            assert {t.lower() for t in view["source_tables"]} <= found, (db, view["name"], view["source_tables"], found)


def test_gap_group_uses_the_most_serious_gap():
    from scripts.analyze_view_extension import gap_group

    assert gap_group(["column:a.b", "table:c"]) == "table"
    assert gap_group(["join:a+b", "column:a.b"]) == "column"
    assert gap_group(["join:a+b"]) == "join"
    assert gap_group([]) == "none"


def test_mcnemar_is_exact_and_two_sided():
    from scripts.analyze_view_extension import mcnemar

    result = mcnemar([True] * 8 + [False] * 2, [False] * 8 + [True] * 2)
    assert result["a_only"] == 8 and result["b_only"] == 2
    assert abs(result["p"] - 0.109375) < 1e-9, result
    assert mcnemar([True], [True])["p"] == 1.0


if __name__ == "__main__":
    failed = 0
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_"):
            try:
                test()
                print("PASS", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, repr(exc)[:500])
    sys.exit(1 if failed else 0)
