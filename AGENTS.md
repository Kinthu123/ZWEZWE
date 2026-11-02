# Folio Help Desk (RAG Q&A)

A local RAG question answering service for Folio, a fictional ebook and audiobook reading service (class assignment). Scope: `docs/scope/scope.md`.

## Stack

- **Language / Runtime**: Python 3.13 (Homebrew), in `.venv`
- **Framework**: FastAPI, run by uvicorn (one worker); serves the API and `web/index.html`
- **Key dependencies**: `ollama` (client for local Ollama: `embeddinggemma` embeddings, `qwen3:8b` chat), `chromadb` (persistent store in `chroma_db/`), `pydantic`
- **Package manager**: pip, pinned in `requirements.txt`
- Full decision and runtime rules: [spec 0001](docs/specs/0001-stack-architecture.md)

## Build approach

Tracer Bullet (get one real question flowing from the web page through retrieval and the LLM and back first, then thicken each part end to end).

## Commands

```bash
# Install (needs Ollama running, models pulled: ollama pull embeddinggemma && ollama pull qwen3:8b)
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Dev server (watch only app/, so writes to chroma_db/ or the log never restart it)
.venv/bin/uvicorn app.main:app --reload --reload-dir app

# Demo on the LAN
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Lint and format (run by hand before committing)
.venv/bin/ruff check . && .venv/bin/ruff format .

# Test: no suite (Alpha tier); each feature is proven with /check verify on the real app
```

## Specs

Stored in `docs/specs/`. Format: `docs/specs/NNNN-title.md`.

## Rules

- Functional style: small modules of plain functions. Push I/O (Ollama, Chroma, files) to the edges; keep chunking, prompt building, and formatting pure.
- No shared mutable state, except the module level clients spec 0001 allows (one Ollama `Client`, one Chroma `PersistentClient`) and constants in `app/config.py`.
- Every setting lives in `app/config.py`, overridable by environment variable; never hardcode a model name, path, or limit elsewhere. Paths resolve from the project root.
- Endpoints are plain `def` (FastAPI runs them in a thread pool); never call the blocking Ollama or Chroma clients inside `async def`.
- Type hints on every function signature; Pydantic models for request and response bodies. No type checker.
- One error pattern: expected failures raise `HTTPException` with JSON `{"detail": ...}`: 422 bad input, 503 Ollama unreachable, 504 Ollama timeout. Never return a raw stack trace.
- A one line docstring on every public function and module.
- Ruff for lint and format, default rules, line length 120.

## Tooling

- Ruff (lint + format), configured in `pyproject.toml`, pinned in `requirements-dev.txt`. No pre-commit hook, no CI, no test runner yet.

## Git

- integration: on
- branch prefix: feat/
- commit: per-milestone

## Agent skills

No tool skills installed. Agent Skills and MCP servers for FastAPI, Chroma, and Ollama deferred ("not now").

## Context files

<!-- Nested AGENTS.md files are listed here as they are created -->

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
