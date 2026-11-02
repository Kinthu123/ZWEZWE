"""Append one JSON line per question to the question log; a logging failure never reaches the caller."""

import json
import logging
import threading
from datetime import UTC, datetime

from app import config

logger = logging.getLogger("folio.log")
_lock = threading.Lock()


def log_question(question: str, *, status: int, model: str | None, sources: list[str], latency_ms: int) -> None:
    """Record a question with its outcome, sources, and latency as one JSON line."""
    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "question": question,
        "status": status,
        "model": model,
        "sources": sources,
        "latency_ms": latency_ms,
    }
    try:
        with _lock, config.LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Could not write to the question log %s: %s", config.LOG_FILE, exc)
