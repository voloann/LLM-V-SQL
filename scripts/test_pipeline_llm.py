"""Tests for model profiles and pipeline step events. Run: python scripts/test_pipeline_llm.py"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config
import llm_client
import model_registry
import v_sql_pipeline_LLM as pipeline
from run_experiment import load_db_configs


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
        choice = types.SimpleNamespace(message=types.SimpleNamespace(content="```sql\nSELECT 1;\n```"))
        return types.SimpleNamespace(usage=usage, choices=[choice])


def with_fake_client():
    completions = FakeCompletions()
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))
    original = llm_client.get_client
    llm_client.get_client = lambda profile=None: client
    return completions, lambda: setattr(llm_client, "get_client", original)


def test_default_call_keeps_max_tokens():
    completions, restore = with_fake_client()
    try:
        sql, stats = llm_client.call_llm("p")
    finally:
        restore()
    assert sql == "SELECT 1", sql
    assert completions.kwargs["max_tokens"] == config.MAX_TOKENS
    assert "max_completion_tokens" not in completions.kwargs
    assert stats["prompt_tokens"] == 11


def test_luna_profile_uses_completion_tokens_and_reasoning_none():
    completions, restore = with_fake_client()
    profile = llm_client.LLMProfile(model="gpt-6-luna", base_url="u", api_key="k", token_param="max_completion_tokens", extra={"reasoning_effort": "none"})
    try:
        llm_client.call_llm("p", profile=profile)
    finally:
        restore()
    assert completions.kwargs["model"] == "gpt-6-luna"
    assert completions.kwargs["max_completion_tokens"] == config.MAX_TOKENS
    assert "max_tokens" not in completions.kwargs
    assert completions.kwargs["reasoning_effort"] == "none"
    assert completions.kwargs["temperature"] == 0.0


def test_error_text_never_contains_the_api_key():
    class Boom:
        def create(self, **kwargs):
            raise RuntimeError("Incorrect API key provided: sk-secret123. Also secret-value")

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Boom()))
    original = llm_client.get_client
    llm_client.get_client = lambda profile=None: client
    try:
        _, stats = llm_client.call_llm("p", profile=llm_client.LLMProfile(model="m", base_url="u", api_key="secret-value"))
    finally:
        llm_client.get_client = original
    assert "sk-secret123" not in stats["error"] and "secret-value" not in stats["error"], stats["error"]


def test_registry_cost_uses_per_million_prices():
    assert abs(model_registry.estimate_cost("gpt-6-luna", 1_000_000, 1_000_000) - 0.60) < 1e-9
    assert model_registry.estimate_cost("qwen2.5-coder-32b-16k", 1_000_000, 1_000_000) == 0


def test_public_model_list_never_exposes_keys():
    for model in model_registry.list_models():
        assert "api_key" not in model and "key_file" not in model, model


def fake_llm(outputs, prompts):
    def call(prompt):
        prompts.append(prompt)
        return outputs[len(prompts) - 1], {"prompt_tokens": 5, "completion_tokens": 2, "latency_s": 0.1, "raw_content": "raw", "error": None}

    return call


def test_vsql_emits_steps_in_order_and_keeps_return_shape():
    cfg = load_db_configs(view_mode="fk", schema_mode="described")["toxicology"]
    prompts, events = [], []
    dummy, final, trace = pipeline.run_v_sql_inference(
        "How many atoms?",
        cfg,
        "hint",
        llm=fake_llm(["SELECT COUNT(*) FROM v_atom_molecule", "SELECT COUNT(*) FROM atom"], prompts),
        on_event=lambda step, status, data: events.append((step, status, data)),
    )
    assert dummy.startswith("SELECT COUNT(*) FROM v_atom") and final == "SELECT COUNT(*) FROM atom"
    assert trace["stage2"]["used_views"] == ["v_atom_molecule"]
    assert [(s, st) for s, st, _ in events] == [
        ("stage1", "running"), ("stage1", "done"), ("linking", "done"), ("stage2", "running"), ("stage2", "done"),
    ]
    assert events[0][2]["prompt"] == prompts[0]
    assert "hint" in prompts[0]
    assert events[1][2]["raw"] == "raw"
    assert events[2][2]["used_views"] == ["v_atom_molecule"]
    assert "CREATE TABLE" in events[2][2]["tables"]
    assert events[3][2]["prompt"] == prompts[1]


def test_direct_emits_steps():
    cfg = load_db_configs(view_mode="manual", schema_mode="names")["toxicology"]
    prompts, events = [], []
    final, trace = pipeline.run_direct_baseline_inference(
        "How many atoms?", cfg, "", llm=fake_llm(["SELECT 2"], prompts), on_event=lambda s, st, d: events.append((s, st, d))
    )
    assert final == "SELECT 2" and trace["joins"] == 0
    assert [(s, st) for s, st, _ in events] == [("direct", "running"), ("direct", "done")]


if __name__ == "__main__":
    failed = 0
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_"):
            try:
                test()
                print("PASS", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, repr(exc)[:400])
    sys.exit(1 if failed else 0)
