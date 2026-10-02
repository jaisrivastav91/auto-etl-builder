import asyncio, pytest
from harness.runtime import run_agent
from evals.golden_set import GOLDEN
from agents.judge import judge_model
from rag.retriever import corrective_retrieve
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval

# (a) end-to-end multi-agent success
@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_pipeline_builds(case):
    report = asyncio.run(run_agent(case["base_url"], case["endpoints"], thread_id=case["name"]))
    assert "Validation passed: True" in report, report

# (b) LLM-as-judge calibration: a deliberately bad model must fail; a good one must pass
def test_judge_rejects_bad_model():
    bad = "select * from raw.pokemon"
    res = asyncio.run(judge_model("raw.pokemon", bad))
    assert res["passed"] is False and res["score"] < 0.75, res

def test_judge_accepts_good_model():
    good = "select cast(id as bigint) as pokemon_id, name as pokemon_name from raw.pokemon"
    res = asyncio.run(judge_model("raw.pokemon", good))
    assert res["passed"] is True, res

# (c) CRAG retrieval quality: the right convention doc is surfaced and graded relevant
def test_crag_finds_conventions():
    out = asyncio.run(corrective_retrieve("dbt staging naming conventions and casting"))
    assert any(d["source"] == "dbt_conventions.md" for d in out["docs"]), out["trace"]
    assert out["fallback"] is False, out["trace"]

# (c2) BM25 / hybrid: an EXACT-token query the dense retriever can miss.
# This is the head-to-head that teaches what BM25 adds.
def test_bm25_catches_exact_tokens():
    from rag.retriever import retrieve
    q = "stg_ prefix and cast id as BIGINT" # literal identifiers, not paraphrase
    bm25_hits = [d["source"] for d in retrieve(q, 4, mode="bm25")]
    hybrid_hits = [d["source"] for d in retrieve(q, 4, mode="hybrid")]
    assert "dbt_conventions.md" in bm25_hits, bm25_hits
    # hybrid must not lose what BM25 found
    assert "dbt_conventions.md" in hybrid_hits, hybrid_hits

# (c3) hybrid is a superset-in-spirit: it recovers the union's best of both retrievers
def test_hybrid_covers_both_signals():
    from rag.retriever import retrieve
    q = "how should I name and type staging columns" # semantic + some tokens
    dense = {d["id"] for d in retrieve(q, 4, mode="dense")}
    bm25 = {d["id"] for d in retrieve(q, 4, mode="bm25")}
    hybrid = {d["id"] for d in retrieve(q, 4, mode="hybrid")}
    # RRF should pull in ids ranked highly by either retriever
    assert hybrid & dense and hybrid & bm25, (dense, bm25, hybrid)

# (d) report usefulness (GEval, an LLM judge inside the eval harness)
def test_report_quality():
    report = asyncio.run(run_agent("https://pokeapi.co/api/v2/", ["pokemon", "type"]))
    metric = GEval(
        name="ReportUsefulness",
        criteria="States source, tables with counts, models, judge scores, and pass/fail.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT], threshold=0.7
    )
    assert_test(LLMTestCase(input="report", actual_output=report), [metric])