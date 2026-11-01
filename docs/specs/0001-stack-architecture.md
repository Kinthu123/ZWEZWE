# 0001. Local Python monolith for the Resonance RAG service

**Date**: 2026-11-01
**Status**: Accepted

## Summary

The Resonance help desk runs as one small Python app on your laptop. FastAPI (a Python web framework) serves both the API and the single web page, Ollama (a local model server) runs the embedding model and a larger chat model, `qwen3:8b`, and Chroma (a vector database, which finds text by meaning) stores the indexed help documents on disk. Everything runs offline on one machine, starts with one command, and can be opened from another device on the same Wi-Fi so your instructor can try it in class.

## Context

The assignment asks for a question answering system over at least six documents about a fictional service (here Resonance, a music streaming service), using a different or larger LLM than the class example, with an API and a web client. It must be demonstrated on video and tried live by the instructor during a class presentation.

The forces are a single developer, one laptop (Apple M4, 16 GB of memory), no budget for hosted APIs, a short timeline, and a live demo where the instructor uses the system on the spot. The class tutorial established a working pattern (Python, FastAPI, Ollama, Chroma), and a grader or instructor should be able to reproduce the setup with standard tools.

The demo also creates a networking need: whoever tries the system must be able to reach it without being handed files or extra setup. And the chat model must fit in memory next to the embedding model and still answer within a few seconds, or the live demo stalls.

Without a recorded stack, each later feature would make its own choices about layout, configuration, and how the page talks to the API, and the pieces would drift apart.

## Options considered

### Option 1: Local Python monolith, FastAPI serves API and page (the tutorial stack, tidied)

One Python package (`app/`) holding config, embeddings, vector store, RAG logic, and the FastAPI app. FastAPI also serves `web/index.html` at `/`. Ollama runs locally; Chroma persists to a local folder. Settings live in one config module with environment variable overrides.

**Pros**:
- Matches what the class taught, so it is easy to explain in the presentation.
- One process, one URL, no CORS (cross origin rules that block a page from calling a different address) setup needed for the page.
- Fully offline and free; no accounts or keys.

**Cons**:
- Everything shares one laptop's memory; a larger model slows answers.
- No auth, so anyone on the same network can call the API, including the document upload.

### Option 2: Flat tutorial files plus a page opened as a local file

The tutorial exactly: `embeddings.py`, `vector_store.py`, `rag.py`, `main.py` at the root, constants inside each file, and `index.html` opened straight from disk calling the API with CORS.

**Pros**:
- One to one with the article; least thinking.
- Nothing extra to design.

**Cons**:
- The instructor must be sent the HTML file and have it point at your IP.
- Settings are scattered, so swapping the model during a demo means editing code.

### Option 3: Separate frontend framework plus API

A JavaScript framework app for the client (with its own build step and dev server) talking to the FastAPI backend.

**Pros**:
- Richer UI tooling and components.

**Cons**:
- Two toolchains, two servers, and a build step for a single Q&A page.
- More to install for anyone reproducing the project, and more to break during a live demo.

### Option 4: Hosted LLM API instead of Ollama

Keep FastAPI and Chroma, but call a hosted model provider for embeddings and answers.

**Pros**:
- Much larger models and faster answers.

**Cons**:
- Needs an account, a key, internet, and money; fails if the classroom network is poor.
- Moves away from the local Ollama setup the course is built on.

## Decision

**Chosen option**: Option 1: Local Python monolith, FastAPI serves API and page.

Build the service as a single Python 3.13 package served by FastAPI and uvicorn, using local Ollama models (`embeddinggemma` for embeddings, `qwen3:8b` for answers) and a persistent local Chroma store, with the web page served from the same app.

## Rationale

The live demo is the riskiest moment, so the stack minimizes moving parts: one process, one URL, no internet. Serving the page from FastAPI means the instructor types one address (your laptop's IP and port) and everything works, which beats Option 2, where you hand over a file and hope its API address is right. Option 3 adds a second toolchain to solve a problem one HTML page does not have.

Staying on Ollama keeps the course's local model setup and avoids keys, cost, and classroom Wi-Fi risk (Option 4). `qwen3:8b` meets the "different or larger model" rule (8 billion parameters against the class's 1.7 billion), fits comfortably in 16 GB next to the embedding model, and supports turning thinking off, so the tutorial's generation pattern still applies. A small `app/` package with one config module keeps the tutorial's module split while making settings (models, chunk size, top_k) changeable by environment variable, so you can swap models during a demo without editing code.

A venv with pinned `requirements.txt` is the most widely reproducible setup for a grader; uv would be faster but is one more tool to install.

## Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Architecture | Single process monolith, one Python package `app/` | One developer, one laptop, one demo; nothing to coordinate. |
| Language | Python 3.13 | The course's version, and every library here supports it. |
| Web framework | FastAPI, run by uvicorn | Typed request validation (via Pydantic) and automatic docs at `/docs` for the presentation. |
| Web client | One static `web/index.html`, served by FastAPI at `/` | Same address as the API, so no CORS setup and no file handoff. Look and layout are decided in the web client design spec. |
| Embedding model | `embeddinggemma` on Ollama | The course's embedding model; small and already pulled. |
| Chat model | `qwen3:8b` on Ollama | Larger than the class's `qwen3:1.7b`, fits in 16 GB, and supports turning thinking off. |
| Model server | Ollama, local at `http://localhost:11434` | Free, offline, already installed (0.30.11). |
| Vector store | Chroma, persistent client writing to `chroma_db/` | Embedded in the app process, so there is no server to run. Record shape is decided in the knowledge record shape spec. |
| Knowledge source | Plain `.txt` files in `knowledge/` | Easy to write, read, and show in the presentation. |
| Configuration | `app/config.py` defaults, overridable by environment variables | One place for settings, and models can be swapped without code edits. |
| Dependencies | `.venv` plus pinned `requirements.txt` (`ollama`, `chromadb`, `fastapi`, `uvicorn[standard]`, `pydantic`) | Standard and reproducible with only Python installed; pinning guards against Chroma API drift between versions. |
| Running | Dev: `uvicorn app.main:app --reload --reload-dir app`. Demo: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (one worker) | Localhost while building; binding to all interfaces lets devices on the same Wi-Fi reach it. |
| Observability | Python standard `logging` to the console, plus the question log feature | Enough to debug locally and to show usage in class. |
| Auth | None | A local classroom demo with no user accounts (see Consequences). |

**Project layout** (what the scaffold creates; later features fill the modules):

```
app/
  __init__.py
  config.py        # all settings, env overridable
  embeddings.py    # Ollama embedding calls
  vector_store.py  # chunking, Chroma storage, retrieval
  rag.py           # prompt building and answer generation
  main.py          # FastAPI app, endpoints, serves web/
web/
  index.html       # the Q&A page
knowledge/         # the Resonance .txt documents
chroma_db/         # created at startup, gitignored
questions.log      # created on first question, gitignored
requirements.txt
```

**Configuration required** (defaults in `app/config.py`, read with plain `os.environ`, no `.env` file and no extra settings library):
- `OLLAMA_HOST`: model server address (default `http://localhost:11434`). Passed explicitly to the Ollama `Client(host=..., timeout=...)`, never left to an implicit read.
- `RAG_EMBED_MODEL`: embedding model name (default `embeddinggemma`).
- `RAG_CHAT_MODEL`: chat model name (default `qwen3:8b`).
- `RAG_TEMPERATURE`: sampling temperature for answers (default `0.2`).
- `RAG_NUM_CTX`: context window sent to Ollama (default `8192`). Ollama's own default is small and silently cuts off long prompts, which would drop retrieved chunks.
- `RAG_KEEP_ALIVE`: how long Ollama keeps a model loaded after a call (default `30m`). The 5 minute default would unload the model in the middle of a demo.
- `RAG_OLLAMA_TIMEOUT`: seconds before an Ollama call is abandoned (default `120`).
- `RAG_KNOWLEDGE_DIR`, `RAG_CHROMA_DIR`, `RAG_LOG_FILE`: paths (defaults `knowledge/`, `chroma_db/`, `questions.log`).
- Retrieval and chunking settings (chunk size, overlap, top_k) also live here; their values are decided in the knowledge record shape spec.

## Runtime rules

These hold for every feature built on this stack.

- **Anchored paths.** Every path in config resolves from the project root (`Path(__file__).resolve().parent.parent`), so the app works no matter which folder uvicorn is started from. Environment variables may override them.
- **Sync endpoints.** Endpoints are plain `def`, not `async def`, and use the sync Ollama `Client` and Chroma client. FastAPI runs plain `def` endpoints in a thread pool, so a 10 second generation never freezes `/health` or the page. Never call a blocking client inside `async def`.
- **One explicit Ollama client.** Built once in `app/embeddings.py` / `app/rag.py` from config (host, timeout). Every chat call passes `think=False` (qwen3 otherwise writes long hidden reasoning that is slow and can leak into answers), `keep_alive`, and `options` with `temperature` and `num_ctx`. Embeddings use `client.embed(...)`, never the older `embeddings(...)` call, which returns a different shape.
- **One Chroma client, one worker.** A single module level `chromadb.PersistentClient` at the anchored `chroma_db/` path. The collection is created with `embedding_function=None` and vectors are always supplied by the app, so Chroma never tries to download its own default model (which breaks offline). uvicorn always runs one worker; never `--workers N`, since Chroma's on disk store is not safe across processes.
- **Startup lifecycle.** A FastAPI `lifespan` hook runs once at startup: index `knowledge/`, then send one tiny warm up chat call so the first real question does not wait for the model to load. If Ollama is unreachable, the app still boots, logs a warning, and `/health` reports Ollama as down; `/ask` and `/search` return 503 until it is reachable. How indexing avoids duplicates is decided in the knowledge record shape spec.
- **Reload safely.** The dev command watches only code: `uvicorn app.main:app --reload --reload-dir app`, so writes to `chroma_db/` or the log never trigger a restart loop.
- **Serving the page.** An explicit `GET /` route returns `web/index.html` with `FileResponse`. No static mount at `/` (it would hide `/docs` and the API). The page calls the API with relative URLs (`/ask`), so it works on whichever host and port it was loaded from.
- **URL scheme and errors.** API paths are flat (`/health`, `/search`, `/ask`, `/documents`), no version prefix. Errors are JSON from `HTTPException` (`{"detail": ...}`): 422 for invalid input (FastAPI's own validation), 503 when Ollama is unreachable, 504 when an Ollama call times out.
- **Prerequisites, not magic.** Ollama must be running and the models pulled (`ollama pull embeddinggemma`, `ollama pull qwen3:8b`) before the app starts; the README lists this. "One command" means one command to start the app once those exist.
- **Recovery.** If the Chroma store is ever corrupted or locked (for example the server was killed mid write), stop the app, delete `chroma_db/`, and start again; it indexes from `knowledge/` on boot.

## Consequences

**Positive**:
- One command starts everything; the demo has no external dependency beyond your laptop and Wi-Fi.
- Swapping the chat model (for example to compare against `qwen3:1.7b` in the presentation) is an environment variable, not a code change.
- The automatic `/docs` page gives you a ready made API demo.

**Negative / tradeoffs**:
- No auth: anyone on the same network while the demo server runs can call every endpoint, including adding or replacing documents. Acceptable for a classroom demo; only run the LAN command while presenting.
- `qwen3:8b` answers more slowly than the class model, and the first question after startup also waits for the model to load into memory (a cold start). Warming the model before the demo is worth planning in demo readiness.
- Index, log, and models live only on this laptop; nothing is backed up or shared.
- The embedding model is fixed once documents are indexed; changing `RAG_EMBED_MODEL` later means deleting `chroma_db/` and indexing again.

**Neutral**:
- `qwen3:8b` (about 5 GB) must be pulled before first run; check with `ollama list`.
- Memory: `qwen3:8b` (about 5.2 GB) plus its context cache plus `embeddinggemma` (about 0.6 GB) fits in 16 GB with other heavy apps closed; a much larger `RAG_NUM_CTX` risks swapping. Expect roughly 8 to 10 seconds for a typical answer once warm.

## Follow-up

- [ ] Agent Skills and MCP servers for FastAPI, Chroma, and Ollama were deferred ("not now"). You can look for them later; a skill would give `/develop` each tool's current conventions instead of relying on memory.
- [ ] For the knowledge record shape spec: `embeddinggemma` expects different task prefixes for queries and for documents (skipping them hurts retrieval quality), and the Chroma collection must set cosine distance explicitly (its default is L2, which makes scores misleading).
- [ ] For demo readiness: rehearse LAN access before class. Allow the macOS firewall prompt for Python, find the IP with `ipconfig getifaddr en0`, keep the laptop awake with `caffeinate -i`, test from a phone, and have a fallback (phone hotspot, since classroom Wi-Fi often isolates devices from each other).
