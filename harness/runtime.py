import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from agent.graph import build_graph
from harness.checkpointer import get_checkpointer

SERVERS = {
    "warehouse": {"command": "python", "args": ["mcp_servers/warehouse_server.py"], "transport": "stdio"},
    "dlt": {"command": "python", "args": ["mcp_servers/dlt_server.py"], "transport": "stdio"},
    "dbt": {"command": "python", "args": ["mcp_servers/dbt_server.py"], "transport": "stdio"},
}

async def _with_retries(coro_fn, attempts=3, base=1.5):
    for i in range(attempts):
        try:
            return await coro_fn()
        except Exception:
            if i == attempts - 1: raise
            await asyncio.sleep(base ** i) # exponential backoff

async def run_agent(base_url: str, endpoints: list[str], thread_id: str = "run-1") -> str:
    client = MultiServerMCPClient(SERVERS)
    tools = await _with_retries(client.get_tools)
    
    with get_checkpointer() as cp:
        app = build_graph(tools, checkpointer=cp)
        final = await app.ainvoke(
            {"api_base_url": base_url, "endpoints": endpoints},
            config={"configurable": {"thread_id": thread_id},
            "recursion_limit": 50}
        ) # hard stop independent of MAX_MODEL_ATTEMPTS
    
    return final["report"]