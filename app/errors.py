"""One place that turns Ollama failures into JSON HTTP errors (503 or 504)."""

import re
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import ollama
from fastapi import HTTPException

_MODEL_NAME = re.compile(r"model ['\"]?([^'\"\s]+)['\"]? not found")


@contextmanager
def ollama_errors() -> Iterator[None]:
    """Map Ollama timeouts, connection failures, and missing models to HTTPException."""
    try:
        yield
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The model server took too long to respond.") from exc
    except (httpx.ConnectError, ConnectionError) as exc:
        raise HTTPException(status_code=503, detail="The model server (Ollama) is not reachable.") from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            match = _MODEL_NAME.search(str(exc.error))
            name = match.group(1) if match else "requested"
            detail = f"Model '{name}' is not available. Pull it with ollama pull {name}."
        else:
            detail = f"The model server returned an error: {exc.error}"
        raise HTTPException(status_code=503, detail=detail) from exc
