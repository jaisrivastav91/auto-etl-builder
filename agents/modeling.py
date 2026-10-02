from langchain_core.messages import HumanMessage
from agent.llm import get_llm
from guardrails.code_safety import assert_sql_safe
from rag.retriever import corrective_retrieve, format_docs
from agents.planner import _strip

_llm = get_llm(temperature=0)

async def generate_model(table: str, columns: list[dict], feedback: str ="", source_key: str | None = None) -> tuple[str, list]:
    crag = await corrective_retrieve(
        f"dbt staging model conventions and column meanings for table {table}",
        source_key=source_key
    ) # <-- global conventions + THIS source's dictionary
    fb = f"\nPrevious attempt feedback to fix:\n{feedback}\n" if feedback else ""
    prompt = (
        f"Conventions, examples & data dictionary:\n{format_docs(crag['docs'])}\n{fb}\n"
        f"Write ONE dbt staging SELECT for source table {table}.\n"
        f"Columns (name,type): {columns}\n"
        "Rules: SELECT only, snake_case business names, explicit casts, no SELECT *. "
        "Return only SQL."
    )
    resp = await _llm.ainvoke([HumanMessage(content=prompt)])
    sql = _strip(resp.content)
    assert_sql_safe(sql) # guardrail
    return sql, crag["trace"]