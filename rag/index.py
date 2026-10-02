import duckdb, glob
import bm25s
from pathlib import Path
from sentence_transformers import SentenceTransformer
from config.settings import (
    DUCKDB_PATH,
    KNOWLEDGE_DIR,
    EMBED_MODEL,
    EMBED_DIM,
    BM25_INDEX_DIR
)

_model = None

def _embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

def _chunk(text, size=800, overlap=150):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size]); i += size - overlap
    return out

def _ensure_kb(con):
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(
        f"CREATE TABLE IF NOT EXISTS kb "
        f"(id BIGINT, kind VARCHAR, source_key VARCHAR, source VARCHAR, "
        f"content VARCHAR, embedding FLOAT[{EMBED_DIM}])"
    )

def _next_id(con):
    return (con.execute("SELECT coalesce(max(id), 0) FROM kb").fetchone()[0] or 0) + 1

def _insert_chunks(con, records):
    m = _embedder()
    for r in records:
        vec = m.encode(r["content"]).tolist()
        con.execute(
            f"INSERT INTO kb VALUES (?, ?, ?, ?, ?, ?::FLOAT[{EMBED_DIM}])",
            [r["id"], r["kind"], r["source_key"], r["source"], r["content"], vec]
        )

def rebuild_bm25():
    """Rebuild the lexical index from ALL kb rows so it stays aligned with dense."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        rows = con.execute(
            "SELECT id, kind, source_key, source, content FROM kb ORDER BY id").fetchall()
    finally:
        con.close()
    records = [
        {"id": i, "kind": k, "source_key": sk, "source": s, "content": c} for i, k, sk, s, c in rows
    ]
    tokens = bm25s.tokenize([r["content"] for r in records], stopwords="en")
    retriever = bm25s.BM25(corpus=records) # store dicts so retrieve() returns them
    retriever.index(tokens)
    retriever.save(BM25_INDEX_DIR)

def build_index():
    """Build the GLOBAL, source-agnostic corpus (conventions + example)."""
    con = duckdb.connect(str(DUCKDB_PATH))
    _ensure_kb(con)
    con.execute("DELETE FROM kb WHERE kind='global'")
    rid, records = _next_id(con), []
    for path in sorted(glob.glob(str(KNOWLEDGE_DIR / "*.md"))):
        for ch in _chunk(Path(path).read_text()):
            records.append(
                {
                    "id": rid,
                    "kind": "global",
                    "source_key": "global",
                    "source": Path(path).name,
                    "content": ch
                }
            )
            rid += 1
    _insert_chunks(con, records)
    con.execute("SET hnsw_enable_experimental_persistence=true;")
    con.execute("CREATE INDEX IF NOT EXISTS kb_hnsw ON kb USING HNSW (embedding) WITH (metric='cosine');")
    con.close()
    rebuild_bm25()
    print(f"indexed {len(records)} global chunks (dense + BM25)")

def index_source_dictionary(source_key: str, markdown: str):
    """Embed a generated per-source data dictionary into kb, then rebuild BM25."""
    con = duckdb.connect(str(DUCKDB_PATH))
    _ensure_kb(con)
    con.execute("DELETE FROM kb WHERE kind='source' AND source_key=?", [source_key])
    rid, records = _next_id(con), []
    for ch in _chunk(markdown):
        records.append(
            {
                "id": rid,
                "kind": "source",
                "source_key": source_key,
                "source": f"sources/{source_key}/data_dictionary.md",
                "content": ch
            }
        )
        rid += 1
    _insert_chunks(con, records)
    con.close()
    rebuild_bm25()

if __name__ == "__main__":
    build_index()