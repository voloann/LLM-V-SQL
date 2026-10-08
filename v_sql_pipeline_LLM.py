# v_sql_pipeline.py
import os
from openai import OpenAI
from prompts import get_stage1_dummy_sql_prompt, get_stage2_reconstruction_prompt
from config import SELECTED_MODEL

LM_STUDIO_URL = "http://localhost:1234/v1"
client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

def clean_sql(text: str) -> str:
    """Loại bỏ markdown, dấu chấm phẩy thừa và đưa câu SQL về một dòng duy nhất."""
    if "```sql" in text:
        text = text.split("```sql")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip().rstrip(";")
    return " ".join(text.split())

def call_local_llm(prompt: str) -> str:
    """Gửi prompt tới Local Model trên LM Studio."""
    try:
        response = client.chat.completions.create(
            model=SELECTED_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800,
        )
        return clean_sql(response.choices[0].message.content)
    except Exception as e:
        print(f"\n[!] Lỗi kết nối LM Studio: {e}")
        return ""

def run_v_sql_inference(question: str, db_config: dict, evidence: str = "") -> tuple[str, str]:
    view_schema = db_config.get("view_schema", "")
    view_mapping = db_config.get("view_mapping_rules", "")
    table_schemas = db_config.get("table_schemas", "")

    # Gộp question và evidence vào prompt theo định dạng chuẩn của BIRD benchmark
    if evidence and evidence.strip():
        augmented_question = f"{question}\nEvidence / External Knowledge: {evidence.strip()}"
    else:
        augmented_question = question

    # In ra console để bạn giám sát chắc chắn evidence đã được nạp
    print(f"-> Input Prompt Question:\n{augmented_question}")

    # Stage 1: Dummy SQL Generation
    prompt_s1 = get_stage1_dummy_sql_prompt(augmented_question, view_schema)
    dummy_sql = call_local_llm(prompt_s1)
    if not dummy_sql:
        dummy_sql = "SELECT 1"

    # Stage 2: SQL Reconstruction
    prompt_s2 = get_stage2_reconstruction_prompt(
        query=augmented_question,
        dummy_sql=dummy_sql,
        view_schemas=view_mapping,
        table_schemas=table_schemas,
        db_type="SQLite"
    )
    final_sql = call_local_llm(prompt_s2)
    if not final_sql:
        final_sql = "SELECT 'INFERENCE_FAILED'"

    return dummy_sql, final_sql