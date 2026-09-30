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

def _chunk(text, size = 800, overlap = 150):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i+size])
        i += size - overlap
    return out

def _collect_chunks() -> list[dict]:
    """One ordered list of {id, source, content} shared by both indexes."""
    records, rid = [], 0
    for path in sorted(glob.glob(str(KNOWLEDGE_DIR / "*.md"))):
        for ch in _chunk(Path(path).read_text()):
            records.append({
                "id": rid,
                "source": Path(path).name,
                "content": ch
            })
            rid += 1
    return records

def build_index():
    records = _collect_chunks()

    # dense index: vectors in DuckDB
    model = SentenceTransformer(EMBED_MODEL)
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(
        f"CREATE OR REPLACE TABLE kb "
        f"(id INTEGER, source VARCHAR, content VARCHAR, embedding FLOAT[{EMBED_DIM}])"
    )

    for r in records:
        vec = model.encode(r["content"]).tolist()
        con.execute(
            f"INSERT INTO kb VALUES (?, ?, ?, ?::FLOAT[{EMBED_DIM}])",
            [r["id"], r["source"], r["content"], vec]
        )
    
    con.execute("SET hnsw_enable_experimental_persistence=true;")
    con.execute(
        "CREATE INDEX IF NOT EXISTS kb_hnsw ON kb USING HNSW (embedding) WITH (metric = 'cosine');"
    )
    con.close()

    # lexical index: BM25 over the identical chunk list
    corpus_tokens = bm25s.tokenize(
        [r["content"] for r in records],
        stopwords = "en"
    )
    retriever = bm25s.BM25(
        corpus = records
    )
    retriever.index(corpus_tokens)
    retriever.save(BM25_INDEX_DIR)

    print(f"indexed {len(records)} chunks (dense + BM25)")

if __name__ == "__main__":
    build_index()