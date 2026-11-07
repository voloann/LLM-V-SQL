"""Tests for the optional "described" schema mode. Run: python scripts/test_schema_described.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config
import v_sql_pipeline_LLM as pipeline
from run_experiment import load_db_configs
from schema_describe import (
    format_tables_described,
    format_view_schema_described,
    load_column_docs,
    view_column_sources,
)


def superhero_views():
    with open("views/manual/superhero.json", encoding="utf-8") as f:
        return json.load(f)["views"]


def test_view_columns_resolve_through_table_aliases():
    sources = view_column_sources(superhero_views()[0])
    assert sources["eye_colour"] == ("colour", "colour"), sources["eye_colour"]
    assert sources["height_cm"] == ("superhero", "height_cm"), sources["height_cm"]


def test_renamed_view_column_resolves_to_its_source_column():
    sources = view_column_sources(superhero_views()[1])
    assert sources["hero_id"] == ("superhero", "id"), sources["hero_id"]


def test_docs_hold_type_and_description():
    docs = load_column_docs(config.DB_ROOT, "superhero")
    entry = docs["superhero"]["height_cm"]
    assert entry["type"] == "INTEGER", entry
    assert entry["description"] == "the height of the superhero", entry


def test_docs_load_for_every_database_including_non_utf8_files():
    for fn in sorted(os.listdir("views/manual")):
        if fn.endswith(".json"):
            db_id = fn[:-5]
            docs = load_column_docs(config.DB_ROOT, db_id)
            assert docs, f"no docs for {db_id}"
    assert load_column_docs(config.DB_ROOT, "financial")["district"]["a3"]["description"] == "region"


def test_described_schema_lists_type_and_description_for_view_columns():
    docs = load_column_docs(config.DB_ROOT, "superhero")
    text = format_view_schema_described(superhero_views(), docs)
    assert "height_cm INTEGER -- the height of the superhero" in text, text
    assert "eye_colour TEXT" in text, text


def test_described_schema_lists_each_view_column_once():
    views = superhero_views()
    text = format_view_schema_described(views, load_column_docs(config.DB_ROOT, "superhero"))
    for view in views:
        assert f"{view['name']}(" in text, view["name"]
    sections = text.split("\n\n")
    assert len(sections) == len(views), sections
    for view, section in zip(views, sections):
        lines = [line.strip() for line in section.splitlines()[1:-1]]
        assert [line.split()[0] for line in lines] == view["columns"], section


def test_described_tables_keep_ddl_and_add_descriptions():
    cfg = load_db_configs(view_mode="manual")["superhero"]
    docs = load_column_docs(config.DB_ROOT, "superhero")
    text = format_tables_described(cfg["table_schemas"], docs)
    assert text.startswith(cfg["table_schemas"]), "DDL must stay intact"
    assert "superhero.height_cm: the height of the superhero" in text, text[-400:]


def test_default_mode_keeps_old_schema():
    cfg = load_db_configs(view_mode="manual")["superhero"]
    assert cfg["view_schema"].splitlines()[0].startswith("v_superhero(id, superhero_name"), cfg["view_schema"]
    assert "direct_schema" not in cfg


def test_described_mode_changes_only_stage1_and_direct_inputs():
    old = load_db_configs(view_mode="manual")["superhero"]
    new = load_db_configs(view_mode="manual", schema_mode="described")["superhero"]
    assert new["view_schema"] != old["view_schema"]
    assert new["direct_schema"] != old["table_schemas"]
    assert new["table_schemas"] == old["table_schemas"], "stage 2 DDL must not change"
    assert new["view_mapping_rules"] == old["view_mapping_rules"], "stage 2 rules must not change"


def capture_prompts(run):
    prompts = []
    real = pipeline.call_llm

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return "SELECT 1", {"completion_tokens": 1, "prompt_tokens": 1, "latency_s": 0.0, "error": None}

    pipeline.call_llm = fake
    try:
        run()
    finally:
        pipeline.call_llm = real
    return prompts


def test_direct_uses_described_schema_when_present():
    cfg = load_db_configs(view_mode="manual", schema_mode="described")["superhero"]
    prompts = capture_prompts(lambda: pipeline.run_direct_baseline_inference("q", cfg))
    assert "superhero.height_cm: the height of the superhero" in prompts[0]


def test_direct_prompt_unchanged_in_default_mode():
    cfg = load_db_configs(view_mode="manual")["superhero"]
    prompts = capture_prompts(lambda: pipeline.run_direct_baseline_inference("q", cfg))
    assert cfg["table_schemas"] in prompts[0]
    assert "superhero.height_cm: the height" not in prompts[0]


def test_vsql_stage1_gets_descriptions_and_stage2_does_not():
    cfg = load_db_configs(view_mode="manual", schema_mode="described")["superhero"]
    prompts = capture_prompts(lambda: pipeline.run_v_sql_inference("q", cfg))
    assert "height_cm INTEGER -- the height of the superhero" in prompts[0]
    assert "-- the height of the superhero" not in prompts[1]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {str(e)[:300]}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
