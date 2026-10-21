import re
import sqlglot
from sqlglot import exp

def parse_views_from_sql(views_sql: str) -> list[dict]:
    """
    Parse chuỗi SQL chứa một hoặc nhiều câu lệnh CREATE VIEW bằng sqlglot.
    Trả về danh sách dict:
    [
        {
            "name": "v_superhero",
            "columns": ["id", "superhero_name", ...],
            "source_tables": ["superhero", "gender", ...],
            "create_sql": "CREATE VIEW v_superhero AS ..."
        },
        ...
    ]
    """
    views = []
    if not views_sql or not views_sql.strip():
        return views
        
    try:
        statements = sqlglot.parse(views_sql, read="sqlite")
    except Exception:
        statements = []

    for stmt in statements:
        if not stmt:
            continue
        # Kiểm tra xem có phải CREATE VIEW không
        is_create_view = False
        if isinstance(stmt, exp.Create):
            kind = str(stmt.args.get("kind", "")).upper()
            if "VIEW" in kind or not kind:
                is_create_view = True
                
        if not is_create_view:
            # Fallback nếu sqlglot phân loại khác nhưng cú pháp bắt đầu bằng CREATE VIEW
            raw_s = stmt.sql(dialect="sqlite").strip()
            if raw_s.upper().startswith("CREATE VIEW"):
                is_create_view = True

        if is_create_view:
            view_name = stmt.this.name if stmt.this else ""
            if not view_name and hasattr(stmt, "this"):
                view_name = str(stmt.this).split()[-1].strip("`\"'")
                
            cols = []
            source_tables = set()
            
            if stmt.expression:
                try:
                    cols = stmt.expression.named_selects
                except Exception:
                    cols = []
                try:
                    for t in stmt.expression.find_all(exp.Table):
                        source_tables.add(t.name.lower())
                except Exception:
                    pass
                    
            views.append({
                "name": view_name,
                "columns": cols,
                "source_tables": sorted(list(source_tables)),
                "create_sql": stmt.sql(dialect="sqlite")
            })
            
    return views

def format_view_schema_header(views: list[dict]) -> str:
    """
    Tạo định dạng schema gọn cho Stage 1:
    v_superhero(id, superhero_name, full_name, ...)
    v_hero_power(hero_id, superhero_name, power_name)
    """
    lines = []
    for v in views:
        name = v.get("name", "")
        cols = v.get("columns", [])
        if cols:
            lines.append(f"{name}({', '.join(cols)})")
        else:
            lines.append(f"{name}")
    return "\n".join(lines)

def count_joins(sql_query: str) -> int:
    """Đếm số phép JOIN trong câu lệnh SQL bằng AST sqlglot, fallback sang regex."""
    if not sql_query or not sql_query.strip():
        return 0
    try:
        tree = sqlglot.parse_one(sql_query, read="sqlite")
        return len(list(tree.find_all(exp.Join)))
    except Exception:
        return len(re.findall(r"\bJOIN\b", sql_query, flags=re.IGNORECASE))

def extract_views_used(dummy_sql: str, available_view_names: list[str]) -> list[str]:
    """
    Xác định danh sách các view thực sự được sử dụng trong dummy SQL.
    Dùng cho bước Schema Linking trong Stage 2 (Figure 1(C) trong paper).
    """
    used = set()
    try:
        tree = sqlglot.parse_one(dummy_sql, read="sqlite")
        for t in tree.find_all(exp.Table):
            t_name = t.name.lower()
            for v in available_view_names:
                if v.lower() == t_name:
                    used.add(v)
    except Exception:
        # Fallback regex nếu dummy_sql có lỗi cú pháp nhẹ
        for v in available_view_names:
            if re.search(rf"\b{re.escape(v)}\b", dummy_sql, flags=re.IGNORECASE):
                used.add(v)
                
    # Nếu không tìm thấy view nào (ví dụ model viết nhầm), trả về toàn bộ view để không thiếu ngữ cảnh
    if not used:
        return available_view_names
    return [v for v in available_view_names if v in used]

def canonical_sql(sql: str) -> str:
    """
    Chuẩn hoá SQL để tính Exact Match (EM-normalized):
    - Chuẩn hoá alias bảng thành tên gốc (hoặc thứ tự lặp)
    - Loại bỏ alias các cột trả về trong SELECT
    - Loại bỏ table prefix nếu câu truy vấn chỉ có 1 bảng duy nhất
    """
    if not sql or not sql.strip():
        return ""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
        seen, alias_map = {}, {}
        for t in tree.find_all(exp.Table):
            name = t.name.lower()
            seen[name] = seen.get(name, 0) + 1
            canon = name if seen[name] == 1 else f"{name}_{seen[name]}"
            if t.alias:
                alias_map[t.alias.lower()] = canon
            t.set("alias", None if canon == name else exp.TableAlias(this=exp.to_identifier(canon)))
            
        for c in tree.find_all(exp.Column):
            if c.table and c.table.lower() in alias_map:
                c.set("table", exp.to_identifier(alias_map[c.table.lower()]))
                
        if len(seen) == 1 and sum(seen.values()) == 1:
            for c in tree.find_all(exp.Column):
                c.set("table", None)
                
        for a in list(tree.find_all(exp.Alias)):
            if isinstance(a.parent, exp.Select):
                a.replace(a.this)
                
        return tree.sql(dialect="sqlite", normalize=True).lower()
    except Exception:
        return " ".join(sql.strip().lower().split())

if __name__ == "__main__":
    # Unit tests
    sql_views = """
    create view v_superhero as select superhero.id, superhero.superhero_name from superhero;
    create view v_hero_power as select hero_power.hero_id, superpower.power_name from hero_power left join superpower on hero_power.power_id = superpower.id;
    """
    parsed = parse_views_from_sql(sql_views)
    assert len(parsed) == 2, f"Expected 2 views, got {len(parsed)}"
    assert parsed[0]["name"] == "v_superhero"
    assert parsed[1]["name"] == "v_hero_power"
    assert "superpower" in parsed[1]["source_tables"]
    
    header = format_view_schema_header(parsed)
    print("Formatted header:\n" + header)
    
    dummy = "SELECT v_hero_power.power_name FROM v_hero_power WHERE v_hero_power.hero_id = 1"
    used = extract_views_used(dummy, ["v_superhero", "v_hero_power"])
    assert used == ["v_hero_power"], f"Expected ['v_hero_power'], got {used}"
    
    joins = count_joins("SELECT * FROM a LEFT JOIN b ON a.id = b.id INNER JOIN c ON b.id = c.id")
    assert joins == 2, f"Expected 2 joins, got {joins}"
    
    print("All sql_utils tests passed!")
