"""Embedding calls to Ollama, with embeddinggemma's document and query prefixes."""

from ollama import Client

from app import config

client = Client(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts in batches of EMBED_BATCH, keeping their order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[start : start + config.EMBED_BATCH]
        response = client.embed(model=config.EMBED_MODEL, input=batch, keep_alive=config.KEEP_ALIVE)
        vectors.extend(list(vector) for vector in response.embeddings)
    if len(vectors) != len(texts):
        raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(vectors)}")
    return vectors


def embed_documents(items: list[tuple[str, str]]) -> list[list[float]]:
    """Embed (title, text) pairs as documents."""
    return _embed([f"title: {title or 'none'} | text: {text}" for title, text in items])


def embed_query(text: str) -> list[float]:
    """Embed a search query."""
    return _embed([f"task: search result | query: {text}"])[0]
