from langchain_core.messages import HumanMessage
from agents.planner import run_planner
from agents.modeling import generate_model
from agents.judge import judge_model
from rag.profile import profile_and_index
from config.settings import MAX_MODEL_ATTEMPTS

def _tool(tools, name):
    for t in tools:
        if t.name == name: return t
    raise KeyError(name)

async def plan_node(state):
    out = await run_planner(state["api_base_url"], state["endpoints"])
    return {"plan": out["plan"], "crag_traces": [out["crag_trace"]], "attempt": 0}

async def ingest_node(state, *, tools):
    plan = state["plan"]
    res = await _tool(tools, "run_rest_api_pipeline").ainvoke(
        {
            "base_url": plan["base_url"],
            "resources": [r["name"] for r in plan["resources"]],
            "data_selector": plan["data_selector"],
            "next_url_path": plan["next_url_path"]
        }
    )
    return {"ingest_result": res}

async def profile_node(state):
    # generate THIS source's data dictionary from the loaded schema + samples, and index it
    source_key = await profile_and_index(state["plan"]["base_url"])
    return {"source_key": source_key}

async def model_node(state, *, tools):
    list_tables = _tool(tools, "list_tables"); describe = _tool(tools, "describe_table")
    write_model = _tool(tools, "write_model")
    source_key = state.get("source_key")
    tables = [
        t for t in await list_tables.ainvoke({}) if t.startswith("raw.") and "_dlt" not in t
    ]
    prev_judge = state.get("judge_results", {})
    models = dict(state.get("models", {}))
    traces = list(state.get("crag_traces", []))
    
    for qn in tables:
        name = "stg_" + qn.split(".", 1)[1]
        # loop engineering: only (re)generate models that don't yet pass
        if prev_judge.get(name, {}).get("passed"):
            continue
        cols = await describe.ainvoke({"qualified_name": qn})
        feedback = prev_judge.get(name, {}).get("feedback","")
        
        sql, tr = await generate_model(qn, cols, feedback, source_key=source_key)
        
        await write_model.ainvoke({"name": name, "sql": sql})
        models[name] = sql; traces.append(tr)
    
    return {"models": models, "crag_traces": traces}

async def judge_node(state):
    source_key = state.get("source_key")
    results = {}
    for name, sql in state["models"].items():
        table = "raw." + name[len("stg_"):]
        results[name] = await judge_model(table, sql, source_key=source_key)
    return {"judge_results": results}

async def build_node(state, *, tools):
    return {"dbt_result": await _tool(tools, "dbt_run").ainvoke({})}

async def validate_node(state, *, tools):
    test = await _tool(tools, "dbt_test").ainvoke({})
    counts = (state.get("ingest_result") or {}).get("tables", {})
    
    empty = [t for t, n in counts.items() if n == 0]
    judges = state.get("judge_results", {})
    
    all_judged_pass = all(v["passed"] for v in judges.values()) if judges else False
    passed = (test["returncode"] == 0 and state["dbt_result"]["returncode"] == 0 and not empty and all_judged_pass)
    
    # accumulate feedback from BOTH the judge and dbt for the next loop iteration
    fb = {
        "attempt": state.get("attempt", 0),
        "failing_models": [n for n, v in judges.items() if not v["passed"]],
        "dbt_test_stderr": test["stderr"][-800:] if test["returncode"] else ""
    }
    
    return {
        "validation": {"passed": passed, "empty_tables": empty, "dbt_test": test},
        "feedback_history": state.get("feedback_history", []) + [fb],
        "attempt": state.get("attempt", 0) + 1
    }

def route_after_validate(state):
    """Loop guard: converge, else revise while budget remains."""
    if state["validation"]["passed"]:
        return "done"
    return "revise" if state["attempt"] <= MAX_MODEL_ATTEMPTS else "done"

async def report_node(state):
    v = state["validation"]; j = state.get("judge_results", {})
    lines = [
        "# ELT build report",
        f"- Source: {state['api_base_url']}",
        f"- Attempts: {state['attempt']}",
        f"- Tables: {(state.get('ingest_result') or {}).get('tables', {})}",
        f"- Models: {list(state.get('models', {}).keys())}",
        f"- Judge scores: {{{', '.join(f'{k}:{x['score']}' for k,x in j.items())}}}",
        f"- CRAG rounds logged: {sum(len(t) for t in state.get('crag_traces', []))}",
        f"- Validation passed: {v['passed']}"
    ]
    
    if v["empty_tables"]: lines.append(f"- ⚠️ Empty tables: {v['empty_tables']}")
    
    return {"report": "\n".join(lines)}