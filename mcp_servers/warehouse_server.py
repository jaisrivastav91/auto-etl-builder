import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from fastmcp import FastMCP
from config.settings import DUCKDB_PATH
from guardrails.code_safety import assert_sql_safe

mcp = FastMCP("warehouse")

@mcp.tool
def list_tables() -> list[str]:
    """List tables as 'schema.table'."""
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        return [
            f"{s}.{t}" for s, t in con.execute("select table_schema, table_name from information_schema.tables").fetchall()
        ]
    finally:
        con.close()

@mcp.tool
def describe_table(qualified_name: str) -> list[dict]:
    """Return [{column, type}] for 'schema.table'."""
    schema, _, table = qualified_name.partition(".")
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        rows = con.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = ? and table_name = ?",
            [schema, table]
        ).fetchall()
        return [
            {
                "column": c,
                "type": t
            }
            for c, t in rows
        ]
    finally:
        con.close()

@mcp.tool
def run_select(sql: str, max_rows: int = 50) -> list[dict]:
    """Read-only SELECT, capped."""
    assert_sql_safe(sql)
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        cur = con.execute(sql)
        cols = [
            d[0] for d in cur.description
        ]
        return [
            dict(zip(cols, r)) for r in cur.fetchmany(max_rows)
        ]
    finally:
        con.close()

if __name__ == "__main__":
    mcp.run()