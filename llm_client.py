import os
import re
import time
from openai import OpenAI
import config

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
    return _client

def clean_sql(text: str) -> str:
    """
    Làm sạch chuỗi SQL trả về từ LLM:
    1. Loại bỏ hoàn toàn khối <think>...</think> (nếu model có thinking mode)
    2. Trích xuất code trong block ```sql ... ``` hoặc ``` ... ```
    3. Loại bỏ dấu chấm phẩy thừa và chuẩn hoá khoảng trắng.
    """
    if not text:
        return ""
    # 1. Loại bỏ khối <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    
    # 2. Trích xuất markdown code block
    if "```sql" in text:
        text = text.split("```sql")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
        
    # 3. Chuẩn hoá khoảng trắng và dấu chấm phẩy
    text = text.strip().rstrip(";")
    return " ".join(text.split())

def call_llm(
    prompt: str,
    temperature: float = config.TEMPERATURE,
    max_tokens: int = config.MAX_TOKENS,
    top_p: float = config.TOP_P,
    model: str = config.SELECTED_MODEL
) -> tuple[str, dict]:
    """
    Gửi prompt tới LLM qua API tương thích OpenAI (LM Studio).
    Trả về: (cleaned_sql, stats_dict)
    stats_dict bao gồm: prompt_tokens, completion_tokens, latency_s, raw_content, error.
    """
    client = get_client()
    stats = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_s": 0.0,
        "raw_content": "",
        "error": None
    }
    
    start_time = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        latency = time.perf_counter() - start_time
        stats["latency_s"] = round(latency, 3)
        
        if response.usage:
            stats["prompt_tokens"] = response.usage.prompt_tokens or 0
            stats["completion_tokens"] = response.usage.completion_tokens or 0
            stats["total_tokens"] = response.usage.total_tokens or 0
            
        raw_content = response.choices[0].message.content or ""
        stats["raw_content"] = raw_content
        cleaned_sql = clean_sql(raw_content)
        return cleaned_sql, stats
        
    except Exception as e:
        stats["latency_s"] = round(time.perf_counter() - start_time, 3)
        stats["error"] = str(e)
        return "", stats

if __name__ == "__main__":
    # Test clean_sql với nhiều định dạng khác nhau
    sample1 = "<think>Let me write the query\n```sql\nSELECT 1;\n```\n</think>```sql\nSELECT superhero.name FROM superhero;\n```"
    assert clean_sql(sample1) == "SELECT superhero.name FROM superhero", f"Failed sample1: {clean_sql(sample1)}"
    
    sample2 = "```\nSELECT * FROM table\n```"
    assert clean_sql(sample2) == "SELECT * FROM table", f"Failed sample2: {clean_sql(sample2)}"
    
    sample3 = "SELECT COUNT(*) FROM hero;"
    assert clean_sql(sample3) == "SELECT COUNT(*) FROM hero", f"Failed sample3: {clean_sql(sample3)}"
    
    print("All clean_sql tests passed!")
