from functools import partial
from langgraph.graph import StateGraph, START, END
from agent.state import ELTState
from agent import nodes

def build_graph(tools, checkpointer=None):
    g = StateGraph(ELTState)
    g.add_node("plan", nodes.plan_node)
    g.add_node("ingest", partial(nodes.ingest_node, tools=tools))
    g.add_node("profile", nodes.profile_node)
    g.add_node("model", partial(nodes.model_node, tools=tools))
    g.add_node("judge", nodes.judge_node)
    g.add_node("build", partial(nodes.build_node, tools=tools))
    g.add_node("validate", partial(nodes.validate_node, tools=tools))
    g.add_node("report", nodes.report_node)
    g.add_edge(START, "plan")
    g.add_edge("plan", "ingest")
    g.add_edge("ingest", "profile") # generate + index this source's data dictionary
    g.add_edge("profile", "model")
    g.add_edge("model", "judge")
    g.add_edge("judge", "build")
    g.add_edge("build", "validate")
    g.add_conditional_edges(
        "validate", nodes.route_after_validate,
        {"revise": "model", "done": "report"}
    ) # <-- the loop
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)