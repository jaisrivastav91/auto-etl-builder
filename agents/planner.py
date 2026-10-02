import json, re
from langchain_core.messages import HumanMessage, SystemMessage
from agent.llm import get_llm
from guardrails.plan_schema import IngestionPlan
from rag.retriever import corrective_retrieve, format_docs

_llm = get_llm(temperature=0)

def _strip(t):
    t = t.strip()
    for f in ("```json", "```sql", "```"):
        if t.startswith(f): t = t[len(f):]
    return t[:-3].strip() if t.endswith("```") else t.strip()

async def run_planner(base_url: str, endpoints: list[str]) -> dict:
    crag = await corrective_retrieve(
        f"How to plan a dlt REST ingestion for endpoints {endpoints}"
    )
    prompt = (
        f"Using these conventions:\n{format_docs(crag['docs'])}\n\n"
        f"API base url: {base_url}\nCandidate endpoints: {', '.join(endpoints)}\n\n"
        "Return STRICT JSON: "
        '{"base_url","data_selector","next_url_path","resources":[{"name","primary_key"}]}'
    )
    resp = await _llm.ainvoke(
        [
            SystemMessage(content="Output only valid JSON."),
            HumanMessage(content=prompt)
        ]
    )
    plan = IngestionPlan.model_validate_json(_strip(resp.content)) # guardrail
    return {"plan": plan.model_dump(), "crag_trace": crag["trace"]}