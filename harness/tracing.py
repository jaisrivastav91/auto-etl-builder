import json, time, functools
from pathlib import Path

RUN_LOG = Path("warehouse/run_log.jsonl")

def traced(node_name):
    """Wrap an async node to emit a structured JSONL span."""
    
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(state, **kw):
            t0 = time.time()
            
            try:
                out = await fn(state, **kw)
                _emit(node_name, "ok", time.time() - t0, out)
                return out
                
            except Exception as e:
                _emit(node_name, "error", time.time() - t0, {"error": repr(e)})
                raise
        return wrapper
    return deco

def _emit(node, status, secs, payload):
    rec = {
        "ts": time.time(), "node": node, "status": status,
        "secs": round(secs, 2), "keys": list(payload.keys())
    }
    
    with RUN_LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")