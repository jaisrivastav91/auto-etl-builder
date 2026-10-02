import re
import duckdb
from urllib.parse import urlparse
from langchain_core.messages import HumanMessage
from agent.llm import get_llm
from config.settings import DUCKDB_PATH, DATA_DICT_SAMPLE_ROWS
from rag.index import index_source_dictionary

_llm = get_llm(temperature=0)

def source_key_from_url(base_url: str) -> str:
    host = urlparse(base_url).netloc or base_url
    return re.sub(r"[^a-z0-9]+", "_", host.lower()).strip("_") # e.g. pokeapi_co

def _schema_and_samples(dataset: str = "raw") -> dict:
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=? AND table_name NOT LIKE '%_dlt%'", [dataset]
        ).fetchall()]
        info = {}
        for t in tables:
            cols = con.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=?", [dataset, t]
            ).fetchall()
            cur = con.execute(f'SELECT * FROM {dataset}."{t}" LIMIT {DATA_DICT_SAMPLE_ROWS}')
            names = [d[0] for d in cur.description]
            sample = [dict(zip(names, row)) for row in cur.fetchall()]
            info[t] = {"columns": cols, "sample": sample}
        return info
    finally:
        con.close()

def _deterministic_md(source_key: str, info: dict) -> str:
    out = [f"# Data dictionary — {source_key}",""]
    for t, d in info.items():
        out.append(f"## raw.{t}")
        out += [f"- `{name}` ({typ})" for name, typ in d["columns"]]
        out.append("")
    return "\n".join(out)

async def build_source_dictionary(source_key: str, dataset: str = "raw") -> str:
    """Let the AGENT derive business meanings from schema + sample rows."""
    info = _schema_and_samples(dataset)
    blob = str(info)[:6000] # keep the prompt small for local models
    prompt = (
        "Write a concise data dictionary for a freshly ingested API source. "
        "For each table and column give a one-line plain-English meaning inferred "
        "from the name, type, and sample values. Output Markdown with a "
        "'## raw.<table>' heading per table and '- `col` (type): meaning' lines.\n\n"
        f"Source: {source_key}\nSchema + sample rows:\n{blob}"
    )
    
    try:
        md = (await _llm.ainvoke([HumanMessage(content=prompt)])).content.strip()
        if "raw." not in md: # empty/weak output -> fall back
            raise ValueError("no usable dictionary")
        return md
    except Exception:
        return _deterministic_md(source_key, info) # robust fallback (esp. tiny local models)

async def profile_and_index(base_url: str, dataset: str = "raw") -> str:
    source_key = source_key_from_url(base_url)
    md = await build_source_dictionary(source_key, dataset)
    index_source_dictionary(source_key, md) # embed + add to kb, rebuild BM25
    return source_key