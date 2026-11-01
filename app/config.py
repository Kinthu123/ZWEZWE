"""All settings in one place. Each one can be overridden by an environment variable."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _path(env_name: str, default: str) -> Path:
    value = Path(os.environ.get(env_name, default))
    return value if value.is_absolute() else PROJECT_ROOT / value


# Ollama
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = float(os.environ.get("RAG_OLLAMA_TIMEOUT", "120"))
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "embeddinggemma")
CHAT_MODEL = os.environ.get("RAG_CHAT_MODEL", "qwen3:8b")
TEMPERATURE = float(os.environ.get("RAG_TEMPERATURE", "0.2"))
NUM_CTX = int(os.environ.get("RAG_NUM_CTX", "8192"))
KEEP_ALIVE = os.environ.get("RAG_KEEP_ALIVE", "30m")

# Chunking and retrieval (spec 0002)
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "80"))
CHUNK_MIN = int(os.environ.get("RAG_CHUNK_MIN", "100"))
EMBED_BATCH = int(os.environ.get("RAG_EMBED_BATCH", "32"))
TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
TOP_K_MAX = int(os.environ.get("RAG_TOP_K_MAX", "10"))
COLLECTION = os.environ.get("RAG_COLLECTION", "resonance_help")

# Answering (spec 0004)
MIN_SCORE = float(os.environ.get("RAG_MIN_SCORE", "0.30"))
MAX_ANSWER_TOKENS = int(os.environ.get("RAG_MAX_ANSWER_TOKENS", "400"))

# Paths
KNOWLEDGE_DIR = _path("RAG_KNOWLEDGE_DIR", "knowledge")
CHROMA_DIR = _path("RAG_CHROMA_DIR", "chroma_db")
LOG_FILE = _path("RAG_LOG_FILE", "questions.log")
WEB_DIR = PROJECT_ROOT / "web"
