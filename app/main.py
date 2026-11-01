"""FastAPI app: serves the API and the web page from one process."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import config, vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("resonance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Resonance Help Desk (chat model %s, embed model %s)", config.CHAT_MODEL, config.EMBED_MODEL)
    status = await asyncio.to_thread(vector_store.rebuild_index)
    logger.info("Index: %s", status)
    yield


app = FastAPI(
    title="Resonance Help Desk",
    description="Ask questions about Resonance, a fictional music streaming service, answered from its help documents.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.WEB_DIR / "index.html")
