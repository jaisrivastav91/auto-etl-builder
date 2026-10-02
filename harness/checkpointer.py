from langgraph.checkpoint.sqlite import SqliteSaver

def get_checkpointer(path: str = "warehouse/graph_state.sqlite"):
    # persists every super-step; lets you resume, inspect, or interrupt runs
    return SqliteSaver.from_conn_string(path)