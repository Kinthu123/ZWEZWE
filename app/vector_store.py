"""Chunking, Chroma storage, and retrieval for the Resonance help documents (spec 0002)."""

import logging
import re
import threading
from datetime import UTC, datetime

import chromadb
from chromadb.config import Settings

from app import config
from app.embeddings import embed_documents, embed_query

logger = logging.getLogger("resonance.index")

SOURCE_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
FILE_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.txt")
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9])")

# ---------- parsing and chunking (pure) ----------


def parse_document(text: str) -> tuple[str, str]:
    """Split raw file text into (title, body); the title is the first non empty line, `#` stripped."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.strip():
            return line.strip().lstrip("#").strip(), "\n".join(lines[index + 1 :]).strip()
    return "", ""


def _paragraphs(body: str) -> list[str]:
    """Blank line separated paragraphs, with runs of spaces collapsed and each line stripped."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", body):
        lines = [re.sub(r" {2,}", " ", line).strip() for line in block.split("\n")]
        paragraph = "\n".join(line for line in lines if line)
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs


def _split_words(text: str, size: int) -> list[str]:
    """Split on spaces; a single word longer than size is cut into size pieces."""
    pieces = []
    for word in text.split():
        pieces.extend(word[i : i + size] for i in range(0, len(word), size))
    return pieces


def _pack(pieces: list[str], size: int, separator: str) -> list[str]:
    """Greedily join pieces with separator into strings of at most size characters."""
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + len(separator) + len(piece) <= size:
            packed[-1] = packed[-1] + separator + piece
        else:
            packed.append(piece)
    return packed


def _split_long(paragraph: str, size: int) -> list[str]:
    """Break an over long paragraph on lines, then sentences, then words, and repack the pieces."""
    pieces = [paragraph]
    splitters = (
        lambda text: text.split("\n"),
        lambda text: _SENTENCE_END.split(text),
        lambda text: _split_words(text, size),
    )
    for splitter in splitters:
        pieces = [part.strip() for piece in pieces for part in (splitter(piece) if len(piece) > size else [piece])]
        pieces = [piece for piece in pieces if piece]
    return _pack(pieces, size, " ")


def _merge_tail(bodies: list[str], size: int, minimum: int) -> list[str]:
    """Fold a too short last chunk into the previous one, or rebalance the two on a word boundary."""
    if len(bodies) < 2 or len(bodies[-1]) >= minimum:
        return bodies
    combined = bodies[-2] + "\n\n" + bodies[-1]
    if len(combined) <= size:
        return bodies[:-2] + [combined]
    middle = len(combined) // 2
    cut = min((i for i, ch in enumerate(combined) if ch.isspace()), key=lambda i: abs(i - middle), default=None)
    if cut is None:
        return bodies
    return bodies[:-2] + [combined[:cut].strip(), combined[cut:].strip()]


def _overlap(previous: str, overlap: int) -> str:
    """The word aligned tail of the previous chunk body, at most overlap characters."""
    if len(previous) <= overlap:
        return previous
    tail = previous[-overlap:]
    space = next((i for i, ch in enumerate(tail) if ch.isspace()), None)
    return "" if space is None else tail[space + 1 :].strip()


def chunk_text(body: str) -> list[str]:
    """Split a document body into paragraph aware chunks with a word aligned overlap."""
    size, overlap = config.CHUNK_SIZE, config.CHUNK_OVERLAP
    units: list[tuple[str, str]] = []
    for paragraph in _paragraphs(body):
        if len(paragraph) <= size:
            units.append((paragraph, "\n\n"))
        else:
            pieces = _split_long(paragraph, size)
            units.extend((piece, "\n\n" if i == 0 else " ") for i, piece in enumerate(pieces))

    bodies: list[str] = []
    for text, separator in units:
        if bodies and len(bodies[-1]) + len(separator) + len(text) <= size:
            bodies[-1] = bodies[-1] + separator + text
        else:
            bodies.append(text)
    bodies = _merge_tail(bodies, size, config.CHUNK_MIN)

    chunks = bodies[:1]
    for previous, current in zip(bodies, bodies[1:], strict=False):
        tail = _overlap(previous, overlap)
        chunks.append(f"{tail}\n{current}" if tail else current)
    return chunks


# ---------- loading files ----------


def load_documents() -> list[tuple[str, str, str]]:
    """Read every valid top level .txt in the knowledge folder as (source, title, body), sorted by source."""
    documents = []
    if not config.KNOWLEDGE_DIR.is_dir():
        logger.warning("Knowledge folder %s does not exist", config.KNOWLEDGE_DIR)
        return documents
    for path in sorted(config.KNOWLEDGE_DIR.iterdir()):
        if path.name.startswith(".") or path.is_dir():
            continue
        if not FILE_PATTERN.fullmatch(path.name) or not path.is_file():
            logger.warning("Skipping %s: name must match [A-Za-z0-9_-]+.txt", path.name)
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping %s: cannot read as UTF-8 (%s)", path.name, exc)
            continue
        source = path.stem
        title, body = parse_document(text)
        if not body:
            logger.warning("Skipping %s: no text after the title line", path.name)
            continue
        documents.append((source, title or source, body))
    return documents


# ---------- Chroma ----------

_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
_lock = threading.Lock()
_status: dict = {"last_rebuild_ok": None, "last_rebuild_at": None, "error": None}


def _open_collection():
    """Open the collection, recreating it once if an older one uses a distance other than cosine."""
    existing = {collection.name for collection in _client.list_collections()}
    if config.COLLECTION in existing:
        collection = _client.get_collection(config.COLLECTION, embedding_function=None)
        space = (collection.configuration.get("hnsw") or {}).get("space")
        if space == "cosine":
            return collection
        logger.warning("Collection %s uses %s distance; recreating it with cosine", config.COLLECTION, space)
        _client.delete_collection(config.COLLECTION)
    return _client.create_collection(
        config.COLLECTION, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
    )


_collection = _open_collection()


def _records(documents: list[tuple[str, str, str]]) -> tuple[list[str], list[str], list[dict], list[tuple[str, str]]]:
    """Turn documents into parallel lists of ids, texts, metadata, and (title, text) pairs to embed."""
    ids, texts, metadatas, items = [], [], [], []
    for source, title, body in documents:
        for position, chunk in enumerate(chunk_text(body)):
            ids.append(f"{source}:{position}")
            texts.append(chunk)
            metadatas.append({"source": source, "title": title, "chunk": position})
            items.append((title, chunk))
    return ids, texts, metadatas, items


def _write(ids: list[str], texts: list[str], metadatas: list[dict], vectors: list[list[float]], where: dict | None):
    """Upsert records, then delete ids (optionally within `where`) that are no longer present. Hold the lock."""
    if ids:
        _collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
    current = set(_collection.get(where=where, include=[])["ids"]) if where else set(_collection.get(include=[])["ids"])
    stale = sorted(current - set(ids))
    if stale:
        _collection.delete(ids=stale)


def index_status() -> dict:
    """Current index state: chunk count and the outcome of the last rebuild."""
    with _lock:
        return {**_status, "chunks": _collection.count()}


def rebuild_index() -> dict:
    """Bring the collection in line with the knowledge folder; on embedding failure leave it untouched."""
    ids, texts, metadatas, items = _records(load_documents())
    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        vectors = embed_documents(items) if items else []
    except Exception as exc:
        logger.warning("Index rebuild failed, keeping the existing index: %s", exc)
        with _lock:
            _status.update(last_rebuild_ok=False, last_rebuild_at=now, error=str(exc))
        return index_status()
    with _lock:
        _write(ids, texts, metadatas, vectors, where=None)
        _status.update(last_rebuild_ok=True, last_rebuild_at=now, error=None)
    return index_status()


def replace_document(source: str, text: str) -> int:
    """Re-index one document from its full text; returns its chunk count. Does not write the file."""
    if not SOURCE_PATTERN.fullmatch(source or ""):
        raise ValueError("Document name must match [A-Za-z0-9_-]+")
    title, body = parse_document(text)
    if not body:
        raise ValueError("Document has no text after its title line")
    ids, texts, metadatas, items = _records([(source, title or source, body)])
    vectors = embed_documents(items)
    with _lock:
        _write(ids, texts, metadatas, vectors, where={"source": source})
    return len(ids)


def search(query: str, top_k: int | None = None) -> list[dict]:
    """Return up to top_k chunks most similar to the query, best first, with a 0 to 1 score."""
    top_k = config.TOP_K if top_k is None else top_k
    if not 1 <= top_k <= config.TOP_K_MAX:
        raise ValueError(f"top_k must be between 1 and {config.TOP_K_MAX}")
    with _lock:
        if _collection.count() == 0:
            return []
    vector = embed_query(query)
    with _lock:
        n_results = min(top_k, _collection.count())
        if n_results == 0:
            return []
        result = _collection.query(
            query_embeddings=[vector], n_results=n_results, include=["documents", "metadatas", "distances"]
        )
    return [
        {
            "text": text,
            "source": metadata["source"],
            "title": metadata["title"],
            "chunk": metadata["chunk"],
            "score": round(min(1.0, max(0.0, 1 - distance)), 3),
        }
        for text, metadata, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        )
    ]
