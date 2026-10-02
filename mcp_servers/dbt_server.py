import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import cast

from fastmcp import FastMCP
from config.settings import DBT_PROJECT_DIR
from guardrails.code_safety import assert_sql_safe

mcp = FastMCP("dbt-runner")

MODELS_DIR = DBT_PROJECT_DIR / "models" / "staging"

def _run(args):
    p = subprocess.run(
        [
            "dbt",
            *args,
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR)
        ],
        capture_output=True, text=True
    )
    
    return {
        "returncode": p.returncode,
        "stdout": p.stdout[-4000:],
        "stderr": p.stderr[-2000:]
    }

@mcp.tool
def write_model(name: str, sql: str) -> dict:
    """Write models/staging/<name>.sql (one SELECT)."""
    if not name.isidentifier():
        return {
            "ok": False,
            "error": "bad name"
        }
    assert_sql_safe(sql)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (MODELS_DIR / f"{name}.sql").write_text(sql)
    return {"ok": True, "path": str(MODELS_DIR / f"{name}.sql")}

@mcp.tool
def dbt_run() -> dict:
    """`dbt run`."""
    return _run(["run"])

@mcp.tool
def dbt_test() -> dict:
    """`dbt test`."""
    return _run(["test"])

if __name__ == "__main__":
    mcp.run()