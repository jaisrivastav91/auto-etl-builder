from typing import TypedDict

class ELTState(TypedDict, total=False):
    api_base_url: str
    endpoints: list[str]
    plan: dict
    source_key: str # derived from the API host; scopes the generated dictionary
    ingest_result: dict
    models: dict # name -> sql
    judge_results: dict # name -> {score, passed, feedback}
    dbt_result: dict
    validation: dict
    feedback_history: list # accumulated across attempts (loop engineering)
    crag_traces: list
    attempt: int
    report: str