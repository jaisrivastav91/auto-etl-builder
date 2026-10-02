import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import cast

import dlt
from dlt.sources.rest_api import rest_api_source
from dlt.sources.rest_api.typing import RESTAPIConfig
from fastmcp import FastMCP
from config.settings import DUCKDB_PATH, MAX_ROWS_PER_RESOURCE

mcp = FastMCP("dlt-runner")

@mcp.tool
def run_rest_api_pipeline(
    base_url: str,
    resources: list[str],
    data_selector: str = "results",
    next_url_path: str | None = "next",
    per_page: int = 100, dataset_name: str = "raw"
) -> dict:
    """Ingest REST resources into DuckDB; return {load_id, tables:{name:rowcount}}."""
    client: dict = {"base_url": base_url}
    if next_url_path:
        client["paginator"] = {"type": "json_link", "next_url_path": next_url_path}
    source = rest_api_source(
        cast(
            RESTAPIConfig,
            {
                "client": client,
                "resource_defaults": {
                    "endpoint": {
                        "data_selector": data_selector,
                        "params": {
                            "limit": per_page
                        }
                    }
                },
                "resources": resources,
            }
        )
    ).add_limit(MAX_ROWS_PER_RESOURCE) # volume guardrail
    
    p = dlt.pipeline(
        pipeline_name="agent_elt",
        destination=dlt.destinations.duckdb(str(DUCKDB_PATH)),
        dataset_name=dataset_name
    )
    info = p.run(source)
    counts = {}
    with p.sql_client() as c:
        for t in p.default_schema.data_table_names():
            rows = c.execute_sql(f"select count(*) from {t}")
            counts[t] = rows[0][0] if rows else 0
            
    return {"load_id": info.loads_ids[0] if info.loads_ids else None, "tables": counts}

if __name__ == "__main__":
    mcp.run()