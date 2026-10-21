import os
import re
import config
from prompts import (
    get_stage1_dummy_sql_prompt,
    get_stage2_reconstruction_prompt,
    get_direct_baseline_prompt
)
from llm_client import call_llm
from sql_utils import count_joins, extract_views_used, parse_views_from_sql

def filter_stage2_schema(dummy_sql: str, db_config: dict) -> tuple[str, str, list[str]]:
    """
    Schema Linking cho Stage 2 (Mục 4.5 của paper):
    Chỉ truyền mapping rule của view được dùng trong dummy SQL và các bảng vật lý liên quan.
    """
    parsed_views = db_config.get("parsed_views", [])
    raw_mapping = db_config.get("view_mapping_rules", "")
    all_table_schemas = db_config.get("table_schemas", "")
    
    if not parsed_views:
        parsed_views = parse_views_from_sql(raw_mapping)
        
    view_names = [v["name"] for v in parsed_views]
    used_views = extract_views_used(dummy_sql, view_names)
    
    # 1. Lọc view mapping rules
    filtered_rules = [v["create_sql"] for v in parsed_views if v["name"] in used_views]
    view_schemas_str = "\n\n".join(filtered_rules) if filtered_rules else raw_mapping
    
    # 2. Lọc relevant table schemas
    linked_tables = set()
    for v in parsed_views:
        if v["name"] in used_views:
            linked_tables.update(v.get("source_tables", []))
            
    # Tách các khối CREATE TABLE trong all_table_schemas
    filtered_tables = []
    for chunk in re.split(r"(?=CREATE\s+TABLE)", all_table_schemas, flags=re.IGNORECASE):
        chunk_clean = chunk.strip()
        if not chunk_clean:
            continue
        match = re.search(r"CREATE\s+TABLE\s+[`\"']?(\w+)[`\"']?", chunk_clean, re.IGNORECASE)
        if match:
            t_name = match.group(1).lower()
            if not linked_tables or t_name in linked_tables:
                filtered_tables.append(chunk_clean)
        else:
            filtered_tables.append(chunk_clean)
            
    table_schemas_str = "\n\n".join(filtered_tables) if filtered_tables else all_table_schemas
    return view_schemas_str, table_schemas_str, used_views

def run_v_sql_inference(question: str, db_config: dict, evidence: str = "") -> tuple[str, str, dict]:
    """
    Thực thi pipeline 2 Stage của V-SQL:
    - Stage 1 (Trước JOIN): Sinh dummy SQL trên view
    - Stage 2 (Sau JOIN): Tái dựng final SQL trên bảng gốc
    Trả về: (dummy_sql, final_sql, trace_info)
    """
    view_schema = db_config.get("view_schema", "")

    # Gộp question và evidence theo chuẩn BIRD
    if evidence and evidence.strip():
        augmented_question = f"{question}\nEvidence: {evidence.strip()}"
    else:
        augmented_question = question

    # --- Stage 1: Dummy SQL Generation ---
    prompt_s1 = get_stage1_dummy_sql_prompt(augmented_question, view_schema)
    dummy_sql, stats_s1 = call_llm(
        prompt=prompt_s1,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
        top_p=config.TOP_P
    )
    if not dummy_sql:
        dummy_sql = "SELECT 1"

    # --- Stage 2: Schema Linking & SQL Reconstruction ---
    view_rules_s2, tables_s2, used_views = filter_stage2_schema(dummy_sql, db_config)
    
    prompt_s2 = get_stage2_reconstruction_prompt(
        query=augmented_question,
        dummy_sql=dummy_sql,
        view_schemas=view_rules_s2,
        table_schemas=tables_s2,
        db_type=config.SQL_DIALECT
    )
    final_sql, stats_s2 = call_llm(
        prompt=prompt_s2,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
        top_p=config.TOP_P
    )
    if not final_sql:
        final_sql = "SELECT 'INFERENCE_FAILED'"

    # Kiểm tra cờ rò rỉ tên view trong final SQL (view_leak)
    has_view_leak = bool(re.search(r"\bv_\w+\b", final_sql, re.IGNORECASE))

    trace_info = {
        "augmented_question": augmented_question,
        "stage1": {
            "dummy_sql": dummy_sql,
            "joins": count_joins(dummy_sql),
            "tokens": stats_s1.get("completion_tokens", 0),
            "prompt_tokens": stats_s1.get("prompt_tokens", 0),
            "latency_s": stats_s1.get("latency_s", 0.0),
            "error": stats_s1.get("error")
        },
        "stage2": {
            "used_views": used_views,
            "final_sql": final_sql,
            "joins": count_joins(final_sql),
            "tokens": stats_s2.get("completion_tokens", 0),
            "prompt_tokens": stats_s2.get("prompt_tokens", 0),
            "latency_s": stats_s2.get("latency_s", 0.0),
            "view_leak": has_view_leak,
            "error": stats_s2.get("error")
        }
    }

    return dummy_sql, final_sql, trace_info

def run_direct_baseline_inference(question: str, db_config: dict, evidence: str = "") -> tuple[str, dict]:
    """
    Thực thi Baseline Direct (E2): sinh SQL trực tiếp trên bảng vật lý cùng prompt style.
    """
    table_schemas = db_config.get("table_schemas", "")
    if evidence and evidence.strip():
        augmented_question = f"{question}\nEvidence: {evidence.strip()}"
    else:
        augmented_question = question
        
    prompt = get_direct_baseline_prompt(augmented_question, table_schemas, db_type=config.SQL_DIALECT)
    final_sql, stats = call_llm(
        prompt=prompt,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
        top_p=config.TOP_P
    )
    if not final_sql:
        final_sql = "SELECT 'INFERENCE_FAILED'"
        
    trace_info = {
        "augmented_question": augmented_question,
        "final_sql": final_sql,
        "joins": count_joins(final_sql),
        "tokens": stats.get("completion_tokens", 0),
        "prompt_tokens": stats.get("prompt_tokens", 0),
        "latency_s": stats.get("latency_s", 0.0),
        "error": stats.get("error")
    }
    return final_sql, trace_info