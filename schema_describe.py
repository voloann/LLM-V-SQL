"""Optional schema text with column types and descriptions (--schema-mode described).

Fields follow Table 6 of the V-SQL paper: data type and column description. Descriptions come from
BIRD's database_description/<table>.csv, types from the database itself.
"""
import csv
import io
import os
import re
import sqlite3

import sqlglot
from sqlglot import exp

MAX_DESCRIPTION_CHARS = 200


def _read_text(path: str) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=encoding, newline="") as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="latin-1", newline="") as f:
        return f.read()


def _read_descriptions(path: str) -> dict[str, str]:
    descriptions = {}
    reader = csv.DictReader(io.StringIO(_read_text(path)))
    for row in reader:
        row = {(k or "").strip(): v for k, v in row.items()}
        name = (row.get("original_column_name") or "").strip().lower()
        text = (row.get("column_description") or "").strip() or (row.get("column_name") or "").strip()
        if name and text:
            descriptions[name] = " ".join(text.split())[:MAX_DESCRIPTION_CHARS]
    return descriptions


def load_column_docs(db_root: str, db_id: str) -> dict:
    """Returns {table_lower: {column_lower: {table, column, type, description}}}."""
    db_dir = os.path.join(db_root, db_id)
    conn = sqlite3.connect(f"file:{os.path.join(db_dir, db_id + '.sqlite')}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        columns = {t: conn.execute(f'PRAGMA table_info("{t}")').fetchall() for t in tables}
    finally:
        conn.close()

    csv_dir = os.path.join(db_dir, "database_description")
    csv_files = {f[:-4].lower(): os.path.join(csv_dir, f) for f in os.listdir(csv_dir) if f.lower().endswith(".csv")} if os.path.isdir(csv_dir) else {}

    docs = {}
    for table, cols in columns.items():
        path = csv_files.get(table.lower())
        descriptions = _read_descriptions(path) if path else {}
        docs[table.lower()] = {
            c[1].lower(): {"table": table, "column": c[1], "type": (c[2] or "").upper(), "description": descriptions.get(c[1].lower(), "")}
            for c in cols
        }
    return docs


def view_column_sources(view: dict) -> dict:
    """Maps each view output column to its (table, column) source, or None for a computed column."""
    tree = sqlglot.parse_one(view["create_sql"], read="sqlite")
    select = tree.expression
    aliases = {(t.alias or t.name).lower(): t.name.lower() for t in select.find_all(exp.Table)}
    tables = list(aliases.values())
    sources = {}
    for projection in select.selects:
        cols = list(projection.find_all(exp.Column))
        source = None
        if len(cols) == 1:
            col = cols[0]
            if col.table:
                source = (aliases.get(col.table.lower(), col.table.lower()), col.name.lower())
            elif len(tables) == 1:
                source = (tables[0], col.name.lower())
        sources[projection.alias_or_name] = source
    return sources


def format_view_schema_described(views: list[dict], docs: dict) -> str:
    """Stage 1 schema: every view column with its type and description, without physical table names."""
    sections = []
    for view in views:
        sources = view_column_sources(view)
        lines = [f"{view['name']}("]
        for column in view["columns"]:
            source = sources.get(column)
            entry = docs.get(source[0], {}).get(source[1]) if source else None
            line = f'  {column}' if re.fullmatch(r"\w+", column) else f'  "{column}"'
            if entry and entry["type"]:
                line += f" {entry['type']}"
            if entry and entry["description"]:
                line += f" -- {entry['description']}"
            lines.append(line)
        lines.append(")")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_tables_described(table_schemas: str, docs: dict) -> str:
    """Direct baseline schema: the original DDL followed by column descriptions."""
    lines = [
        f"-- {entry['table']}.{entry['column']}: {entry['description']}"
        for columns in docs.values()
        for entry in columns.values()
        if entry["description"]
    ]
    return table_schemas + ("\n\n-- Column descriptions\n" + "\n".join(lines) if lines else "")
