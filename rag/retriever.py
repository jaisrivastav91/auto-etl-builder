import os
import duckdb
import bm25s
from sentence_transformers import SentenceTransformer
from langchain_core.messages import HumanMessage
from agent.llm import get_llm
from config.settings import (
    DUCKDB_PATH,
    EMBED_MODEL,
    EMBED_DIM,
    BM25_INDEX_DIR,
    RRF_K,
    RETRIEVAL_MODE,
    MAX_CRAG_ROUNDS,
    CRAG_MIN_RELEVANT
)

_embedder = SentenceTransformer(EMBED_MODEL)
_grader = get_llm(temperature=0)

# BM25 is rebuilt at runtime (per-source dictionary); reload when the dir changes.
_bm25_cache = {"stamp": None, "obj": None}
def _get_bm25():
    stamp = os.path.getmtime(BM25_INDEX_DIR) if os.path.isdir(BM25_INDEX_DIR) else None
    if _bm25_cache["obj"] is None or _bm25_cache["stamp"] != stamp:
        _bm25_cache["obj"] = bm25s.BM25.load(BM25_INDEX_DIR, load_corpus=True)
        _bm25_cache["stamp"] = stamp
    return _bm25_cache["obj"]

def _scope(source_key):
    # rows visible to this query: always global, plus this run's source dictionary
    return ["global"] + ([source_key] if source_key else [])

# --- (a) dense retriever: cosine over DuckDB vectors, scoped ---
def _dense_search(query: str, k: int = 4, source_key: str | None = None) -> list[dict]:
    vec = _embedder.encode(query).tolist()
    keys = _scope(source_key)
    ph = ",".join("?" for _ in keys)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("LOAD vss;")
    try:
        rows = con.execute(
            f"SELECT id, source, content, "
            f"array_cosine_distance(embedding, ?::FLOAT[{EMBED_DIM}]) AS dist "
            f"FROM kb WHERE source_key IN ({ph}) ORDER BY dist LIMIT {k}",
            [vec, *keys]
        ).fetchall()
    finally:
        con.close()
    return [{"id": i, "source": s, "content": c} for i, s, c, _ in rows]

# --- (b) lexical retriever: BM25, scoped (over-fetch then filter) ---
def _bm25_search(query: str, k: int = 4, source_key: str | None = None) -> list[dict]:
    keys = set(_scope(source_key))
    q = bm25s.tokenize(query, stopwords="en")
    docs, _ = _get_bm25().retrieve(q, k=max(k * 4, 8))
    out = []
    for d in docs[0]:
        if d["source_key"] in keys:
            out.append({"id": d["id"], "source": d["source"], "content": d["content"]})
        if len(out) >= k:
            break
    return out

# --- (c) fuse with Reciprocal Rank Fusion ---
def _rrf_fuse(rankings: list[list[dict]], k: int = 4) -> list[dict]:
    scores, meta = {}, {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (RRF_K + rank)
            meta[doc["id"]] = doc
    # top = sorted(scores, key=scores.get, reverse=True)[:k]
    top = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:k]
    return [meta[i] for i in top]

def _hybrid_search(query: str, k: int = 4, source_key: str | None = None) -> list[dict]:
    return _rrf_fuse(
        [
            _dense_search(query, k, source_key),
            _bm25_search(query, k, source_key)
        ],
        k=k
    )

# one switch so evals can compare modes
def retrieve(query: str, k: int = 4, mode: str | None = None, source_key: str | None = None) -> list[dict]:
    mode = mode or RETRIEVAL_MODE
    if mode == "dense": return _dense_search(query, k, source_key)
    if mode == "bm25": return _bm25_search(query, k, source_key)
    return _hybrid_search(query, k, source_key)

# --- CRAG loop (hybrid + scoped) ---
async def _grade(query: str, chunk: str) -> bool: # LLM-as-judge #1
    r = await _grader.ainvoke(
            [
                HumanMessage(
                    content=(
                        f"Question: {query}\n\nDocument:\n{chunk}\n\n"
                        "Is this document relevant and helpful for answering the question? "
                        "Reply with exactly 'yes' or 'no'."
                    )
                )
            ]
    )
    return r.content.strip().lower().startswith("y")

async def _rewrite(query: str) -> str: # correction action
    r = await _grader.ainvoke([HumanMessage(content=(
        f"Rewrite this retrieval query to be clearer and more specific, "
        f"keeping the same intent:\n{query}\nReturn only the rewritten query."))]
    )
    return r.content.strip()

async def corrective_retrieve(query: str, k: int = 4, source_key: str | None = None) -> dict:
    """CRAG over scoped HYBRID retrieval: retrieve -> grade -> (rewrite+refetch)* -> fallback."""
    trace = []
    for round_i in range(MAX_CRAG_ROUNDS + 1):
        hits = retrieve(query, k, source_key=source_key) # hybrid + scoped
        relevant = [h for h in hits if await _grade(query, h["content"])]
        trace.append(
            {
                "round": round_i,
                "query": query,
                "mode": RETRIEVAL_MODE,
                "source_key": source_key,
                "retrieved": len(hits),
                "relevant": len(relevant)
            }
        )
        if len(relevant) >= CRAG_MIN_RELEVANT:
            return {"docs": relevant, "trace": trace, "fallback": False}
        if round_i < MAX_CRAG_ROUNDS:
            query = await _rewrite(query) # corrective step
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        default = con.execute(
            "SELECT id, source, content FROM kb WHERE source='dbt_conventions.md' LIMIT 3"
        ).fetchall()
    finally:
        con.close()
    
    return {
        "docs": [{"id": i, "source": s, "content": c} for i, s, c in default],
        "trace": trace,
        "fallback": True
    }

def format_docs(docs: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{d['source']}]\n{d['content']}" for d in docs)