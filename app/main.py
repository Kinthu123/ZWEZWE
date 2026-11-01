"""FastAPI app: serves the API and the web page from one process."""

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from app import config, question_log, rag, vector_store
from app.errors import ollama_errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("resonance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Resonance Help Desk (chat model %s, embed model %s)", config.CHAT_MODEL, config.EMBED_MODEL)
    status = await asyncio.to_thread(vector_store.rebuild_index)
    logger.info("Index: %s", status)
    await asyncio.to_thread(rag.warm_up)
    yield


app = FastAPI(
    title="Resonance Help Desk",
    description="Ask questions about Resonance, a fictional music streaming service, answered from its help documents.",
    version="0.1.0",
    lifespan=lifespan,
)

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AskRequest(BaseModel):
    question: Question
    top_k: Annotated[int, Field(ge=1, le=config.TOP_K_MAX)] | None = None


class Source(BaseModel):
    source: str
    title: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    latency_ms: int


class SearchRequest(BaseModel):
    query: Question
    top_k: Annotated[int, Field(ge=1, le=config.TOP_K_MAX)] | None = None


class SearchResult(Source):
    text: str
    chunk: int


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    latency_ms: int


class DocumentRequest(BaseModel):
    name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    content: Annotated[str, StringConstraints(min_length=1, max_length=config.MAX_DOC_CHARS)]


class DocumentResponse(BaseModel):
    name: str
    title: str
    chunks: int
    created: bool
    latency_ms: int


class Health(BaseModel):
    status: str
    ollama: bool
    models: dict[str, bool]
    chunks: int
    last_rebuild_ok: bool | None
    last_rebuild_at: str | None
    error: str | None


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.WEB_DIR / "index.html")


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Answer a question about Resonance from its help documents, with sources and timing."""
    start = time.perf_counter()
    try:
        answer, sources, model = _answer(request.question, request.top_k)
    except HTTPException as exc:
        elapsed = round((time.perf_counter() - start) * 1000)
        question_log.log_question(request.question, status=exc.status_code, model=None, sources=[], latency_ms=elapsed)
        raise
    latency_ms = round((time.perf_counter() - start) * 1000)
    question_log.log_question(
        request.question, status=200, model=model, sources=[s["source"] for s in sources], latency_ms=latency_ms
    )
    return AskResponse(answer=answer, sources=sources, model=model, latency_ms=latency_ms)


def _answer(question: str, top_k: int | None) -> tuple[str, list[dict], str]:
    """Retrieve, apply the relevance cutoff, and generate: returns (answer, sources, model)."""
    with ollama_errors():
        hits = vector_store.search(question, top_k)
    if not hits or hits[0]["score"] < config.MIN_SCORE:
        return rag.OFF_TOPIC_ANSWER, [], "retrieval only"
    context = [hit for hit in hits if hit["score"] >= config.MIN_SCORE]
    with ollama_errors():
        answer = rag.generate(question, context)
    return answer, rag.sources_for(context), config.CHAT_MODEL


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Return the most relevant help passages for a query, without calling the chat model."""
    start = time.perf_counter()
    with ollama_errors():
        hits = vector_store.search(request.query, request.top_k)
    latency_ms = round((time.perf_counter() - start) * 1000)
    return SearchResponse(query=request.query, results=hits, latency_ms=latency_ms)


@app.post("/documents", response_model=DocumentResponse)
def upsert_document(request: DocumentRequest) -> DocumentResponse:
    """Add or replace a help document; saved to knowledge/ and searchable immediately. Needs RAG_ALLOW_UPLOADS=1."""
    if not config.ALLOW_UPLOADS:
        raise HTTPException(
            status_code=403,
            detail="Document uploads are turned off. Start the server with RAG_ALLOW_UPLOADS=1 to enable them.",
        )
    start = time.perf_counter()
    target = config.KNOWLEDGE_DIR / f"{request.name}.txt"
    created = not target.exists()
    temp = config.KNOWLEDGE_DIR / f".{request.name}.{secrets.token_hex(4)}.tmp"
    temp.write_text(request.content, encoding="utf-8")
    try:
        with ollama_errors():
            chunks = vector_store.replace_document(request.name, request.content)
        os.replace(temp, target)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        temp.unlink(missing_ok=True)
    title = vector_store.parse_document(request.content)[0] or request.name
    latency_ms = round((time.perf_counter() - start) * 1000)
    return DocumentResponse(name=request.name, title=title, chunks=chunks, created=created, latency_ms=latency_ms)


def _with_tag(name: str) -> str:
    """Ollama lists untagged models as `name:latest`."""
    return name if ":" in name else f"{name}:latest"


@app.get("/health", response_model=Health, responses={503: {"model": Health}})
def health() -> JSONResponse:
    """Report whether Ollama and both models are available, and the state of the index. 503 when degraded."""
    try:
        available = {model.model for model in rag.client.list().models}
        reachable = True
    except Exception as exc:
        logger.warning("Health check could not reach Ollama: %s", exc)
        available, reachable = set(), False
    models = {
        config.EMBED_MODEL: _with_tag(config.EMBED_MODEL) in available,
        config.CHAT_MODEL: _with_tag(config.CHAT_MODEL) in available,
    }
    index = vector_store.index_status()
    healthy = reachable and all(models.values()) and index["chunks"] > 0
    body = Health(status="ok" if healthy else "degraded", ollama=reachable, models=models, **index)
    return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)
