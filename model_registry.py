"""Models the pipeline can call. API keys stay on the server and never appear in list_models()."""
import json
import os
import urllib.request

from llm_client import LLMProfile

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OPENAI_KEY_FILE = os.environ.get("LLM_KEY_FILE", "~/.config/llm-v-sql/llm.key")

MODELS = {
    "gpt-6-luna": {
        "label": "GPT-6 Luna",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "token_param": "max_completion_tokens",
        "extra": {"reasoning_effort": "none"},
        "price_in": 0.10,
        "price_out": 0.50,
        "seconds_per_call": 2.0,
        "note": "Cloud, tính phí theo token, reasoning tắt để giữ temperature 0.",
    },
    "qwen2.5-coder-32b-16k": {
        "label": "Qwen2.5-Coder 32B",
        "provider": "ollama",
        "base_url": f"{OLLAMA_URL}/v1",
        "price_in": 0.0,
        "price_out": 0.0,
        "seconds_per_call": 25.0,
        "note": "Chạy cục bộ, miễn phí, chậm và tốn nhiều RAM.",
    },
    "qwen2.5-coder-16k": {
        "label": "Qwen2.5-Coder 7B",
        "provider": "ollama",
        "base_url": f"{OLLAMA_URL}/v1",
        "price_in": 0.0,
        "price_out": 0.0,
        "seconds_per_call": 5.0,
        "note": "Chạy cục bộ, miễn phí.",
    },
    "qwen3-4b-2507-16k": {
        "label": "Qwen3 4B",
        "provider": "ollama",
        "base_url": f"{OLLAMA_URL}/v1",
        "price_in": 0.0,
        "price_out": 0.0,
        "seconds_per_call": 5.0,
        "note": "Chạy cục bộ, miễn phí, chưa dùng trong các lần chạy chính thức.",
    },
}


def estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    model = MODELS[model_id]
    return (prompt_tokens * model["price_in"] + completion_tokens * model["price_out"]) / 1_000_000


def _read_key() -> str:
    path = os.path.expanduser(OPENAI_KEY_FILE)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _ollama_models() -> set[str] | None:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2.0) as response:
            data = json.loads(response.read().decode())
    except Exception:
        return None
    names = set()
    for item in data.get("models", []):
        names.add(item["name"])
        names.add(item["name"].removesuffix(":latest"))
    return names


def list_models() -> list[dict]:
    """Public model list with availability, safe to send to the browser."""
    installed = _ollama_models()
    has_key = bool(_read_key())
    result = []
    for model_id, model in MODELS.items():
        if model["provider"] == "openai":
            available, reason = has_key, "" if has_key else "Chưa có API key trên server"
        elif installed is None:
            available, reason = False, "Ollama chưa chạy"
        else:
            available = model_id in installed
            reason = "" if available else "Chưa tải model về Ollama"
        result.append(
            {
                "id": model_id,
                "label": model["label"],
                "provider": model["provider"],
                "price_in": model["price_in"],
                "price_out": model["price_out"],
                "seconds_per_call": model["seconds_per_call"],
                "note": model["note"],
                "available": available,
                "unavailable_reason": reason,
            }
        )
    return result


def get_profile(model_id: str) -> LLMProfile:
    model = MODELS[model_id]
    api_key = _read_key() if model["provider"] == "openai" else "ollama"
    if not api_key:
        raise ValueError(f"Thiếu API key cho {model_id}")
    return LLMProfile(
        model=model_id,
        base_url=model["base_url"],
        api_key=api_key,
        token_param=model.get("token_param", "max_tokens"),
        extra=model.get("extra", {}),
    )
