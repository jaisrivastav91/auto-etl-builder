import json
from langchain_core.messages import HumanMessage
from agent.llm import get_llm
from config.settings import JUDGE_THRESHOLD
from rag.retriever import corrective_retrieve, format_docs
from agents.planner import _strip

_judge = get_llm(temperature=0)
_RUBRIC = """You are a senior analytics engineer reviewing a dbt staging model.
Score 0.0-1.0 and return STRICT JSON {{"score": <float>, "feedback": "<one paragraph>"}}.
Criteria: columns renamed to clear snake_case (no raw API names); explicit casts;
no SELECT *; single SELECT reading only from the given source; follows the conventions.
Conventions:\n{conventions}\n
Source table: {table}
SQL:\n{sql}"""

async def judge_model(table: str, sql: str, source_key: str | None = None) -> dict:
    crag = await corrective_retrieve(
        f"review criteria and column meanings for staging model{table}",
        source_key=source_key
    )
    resp = await _judge.ainvoke(
        [
            HumanMessage(
                content=_RUBRIC.format(
                    conventions=format_docs(crag["docs"]), table=table, sql=sql
                )
            )
        ]
    )
    data = json.loads(_strip(resp.content))
    data["passed"] = float(data["score"]) >= JUDGE_THRESHOLD
    return data