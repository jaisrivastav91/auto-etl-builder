import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_DIR = ROOT / "warehouse"
DUCKDB_PATH = WAREHOUSE_DIR / "elt.duckdb"
DBT_PROJECT_DIR = ROOT / "dbt_project"

KNOWLEDGE_DIR = ROOT / "knowledge"
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai_compatible") # openai_compatible | anthropic
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")

# RAG
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
BM25_INDEX_DIR = str(WAREHOUSE_DIR / "bm25_index") # persisted lexical index
RRF_K = int(os.environ.get("RRF_K", "60")) # Reciprocal Rank Fusion constant
RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "hybrid") # dense | bm25 | hybrid
DATA_DICT_SAMPLE_ROWS = int(os.environ.get("DATA_DICT_SAMPLE_ROWS", "5"))

# loop-engineering budgets & thresholds
MAX_MODEL_ATTEMPTS = int(os.environ.get("MAX_MODEL_ATTEMPTS", "3"))
MAX_CRAG_ROUNDS = int(os.environ.get("MAX_CRAG_ROUNDS", "2"))
CRAG_MIN_RELEVANT = int(os.environ.get("CRAG_MIN_RELEVANT", "2"))
JUDGE_THRESHOLD = float(os.environ.get("JUDGE_THRESHOLD", "0.75"))
MAX_ROWS_PER_RESOURCE = int(os.environ.get("MAX_ROWS_PER_RESOURCE", "500"))

WAREHOUSE_DIR.mkdir(exist_ok=True)