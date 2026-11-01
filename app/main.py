"""FastAPI app: serves the API and the web page from one process."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints

from app import config, rag, vector_store
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


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.WEB_DIR / "index.html")


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Answer a question about Resonance from its help documents, with sources and timing."""
    start = time.perf_counter()
    with ollama_errors():
        hits = vector_store.search(request.question, request.top_k)
    if not hits or hits[0]["score"] < config.MIN_SCORE:
        answer, sources, model = rag.OFF_TOPIC_ANSWER, [], "retrieval only"
    else:
        context = [hit for hit in hits if hit["score"] >= config.MIN_SCORE]
        with ollama_errors():
            answer = rag.generate(request.question, context)
        sources, model = rag.sources_for(context), config.CHAT_MODEL
    latency_ms = round((time.perf_counter() - start) * 1000)
    return AskResponse(answer=answer, sources=sources, model=model, latency_ms=latency_ms)
