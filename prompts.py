def get_view_creation_prompt(raw_databse: str) -> str:
    """Prompt tạo View Schema trong module Table Mapping (Figure 2)."""
    return f"""# task
You are a professional database administrator. I need to create views based on "db schema" to eliminate foreign keys as much as possible. Please tell me the SQL without explanation.

notice:
1. All views start with "v_"
2. Don't use alias
3. View don't select other view, use original table only.
4. try to merge relevant tables in order to reduce the frequency of using join

# db schema
{raw_databse}

# format example
```sql
your sql
```"""


def get_stage1_dummy_sql_prompt(query: str, relevant_db_schema: str) -> str:
    """Prompt Stage 1: Dummy SQL Generation từ View (Figure 4)."""
    return f"""# target
You are an experienced database administrator, please answer "question" by sql with no explanation.
notice:
1. Do not alias the output fields
2. must avoid ambiguous column name by using table name and column name in the SQL statement. For example, use 'table_name.column_name' instead of just 'column_name'.
3. refer to "relevant db schema"

# relevant db schema
{relevant_db_schema}

# question
{query}"""


def get_stage2_reconstruction_prompt(
    query: str, 
    dummy_sql: str, 
    view_schemas: str, 
    table_schemas: str, 
    db_type: str = "SQLite"
) -> str:
    """Prompt Stage 2: SQL Reconstruction - phục hồi câu truy vấn trên bảng vật lý (Figure 5)."""
    return f"""# target
According to the "views schemas", "view query" and "relevant table schemas", restore the sql in "view query" to one used the original table query without explanation
notice:
1. SQL should contain "join" as little as possible.
2. table in "views schemas" should not be contained in output.
3. comply with the syntax of {db_type}.
4. must avoid ambiguous column name by using table name and column name in the SQL statement. For example, use 'table_name.column_name' instead of just 'column_name'.

# view schemas
{view_schemas}

# relevant table schemas
{table_schemas}

# view query
Question: {query}
```sql
{dummy_sql}

#format
```sql
{{sql}}
```"""