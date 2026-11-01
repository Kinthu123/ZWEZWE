# Resonance Help Desk

A retrieval augmented generation (RAG) question answering system for **Resonance**, a fictional music streaming service. You ask a question in a web page; the system finds the most relevant passages in Resonance's six help documents and a local LLM answers using only those passages, showing which documents it used and how long it took. Everything runs offline on one laptop.

## Assignment checklist

| Requirement | Where it is |
|---|---|
| A fictional service (not the class company policy example) | Resonance, a music streaming service |
| At least six documents, each on a different topic | [`knowledge/`](knowledge/): plans and pricing, offline downloads, family and student accounts, devices and playback, artists and royalties, refunds and cancellation |
| A RAG system that answers from those documents | [`app/vector_store.py`](app/vector_store.py) (chunking, embeddings, Chroma retrieval) and [`app/rag.py`](app/rag.py) (grounded prompt and generation) |
| A different or larger LLM than in class | `qwen3:8b` (8 billion parameters) instead of the class's `qwen3:1.7b` |
| An API | FastAPI: `POST /ask`, `POST /search`, `GET /health`, `POST /documents`, interactive docs at `/docs` |
| A web client | [`web/index.html`](web/index.html), served at `/` |

## How it works

```
question ──► embed with embeddinggemma ──► Chroma: top 4 chunks by cosine similarity
                                                │
                     best score < 0.30? ── yes ─┴─► "I can only help with questions about Resonance…" (no LLM call)
                                                │ no
                                                ▼
             qwen3:8b with a strict "answer only from these excerpts" prompt
                                                │
                                                ▼
                     answer + source documents + response time ──► web page
```

- **Indexing**: at startup every `knowledge/*.txt` file is split into paragraph aware chunks of about 500 characters (80 characters of overlap), embedded with `embeddinggemma`, and stored in a persistent Chroma collection. The index is brought in line with the files on every start.
- **Retrieval**: the question is embedded with `embeddinggemma`'s query prefix and the 4 most similar chunks are retrieved.
- **Relevance cutoff**: clearly off topic questions (best match below 0.30) are declined instantly without calling the LLM.
- **Generation**: `qwen3:8b` (thinking off, temperature 0.2) answers in a short English paragraph from the excerpts only, or says the documents don't cover it.

Design decisions are recorded in [`docs/specs/`](docs/specs/) and the build plan in [`docs/scope/scope.md`](docs/scope/scope.md).

## Requirements

- macOS, Linux, or Windows with WSL (built and tested on an Apple M4 with 16 GB of memory)
- Python 3.13
- [Ollama](https://ollama.com) 0.11.10 or newer, running locally
- About 7 GB of disk space for the two models

## Setup

```bash
# 1. Pull the models (once)
ollama pull embeddinggemma
ollama pull qwen3:8b

# 2. Create the virtual environment and install dependencies
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

## Run

```bash
# Development (localhost only, reloads on code changes)
.venv/bin/uvicorn app.main:app --reload --reload-dir app

# Live demo (reachable from other devices on the same Wi-Fi, keeps the laptop awake)
./scripts/demo.sh
```

Open http://localhost:8000. Startup takes about 10 seconds while it indexes the documents and loads the model. The demo script prints the address a phone on the same Wi-Fi should use.

## Using the API

Interactive documentation is at http://localhost:8000/docs.

| Endpoint | What it does |
|---|---|
| `POST /ask` | Answer a question: `{"question": "...", "top_k": 4}` (`top_k` optional, 1 to 10) → `answer`, `sources`, `model`, `latency_ms` |
| `POST /search` | Return the most relevant passages without calling the LLM: `{"query": "...", "top_k": 4}` |
| `GET /health` | Ollama reachability, model availability, and index status (200 when healthy, 503 when degraded) |
| `POST /documents` | Add or replace a document: `{"name": "podcasts", "content": "# Podcasts\n\n..."}`. Off by default; start with `RAG_ALLOW_UPLOADS=1` |

```bash
curl -s -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question": "How much is the Family plan?"}'
```

Every question is appended to `questions.log` as one JSON line (time, question, status, model, sources, latency).

## Demo questions

One per document, plus the edge cases. Expected answers come straight from the documents.

| Question | Document | Expected answer |
|---|---|---|
| How much is the Family plan? | Plans and Pricing | $17.99 per month for up to 6 accounts at the same address |
| How many devices can I download music on? | Offline Downloads | Up to 5 devices, up to 10,000 tracks each |
| How long can I stay on the Student plan? | Family and Student Accounts | At most 48 months, reverified every 12 months |
| Does Resonance work on Apple Watch? | Devices and Playback | Yes, watchOS 9 or later, with offline downloads on Premium |
| When do artists get paid? | Artists and Royalties | 45 days after the end of each month, once the balance reaches $10 |
| Can I get a refund on the yearly plan? | Refunds and Cancellation | Full refund within 14 days of the charge; after that, Premium continues to the end of the year |
| What is the capital of France? | (off topic) | Instant refusal, sources empty, `retrieval only` |
| How do I reset my password? | (not covered) | "The help documents don't cover that…" plus a pointer to live chat |

**Adding a document live**: restart with `RAG_ALLOW_UPLOADS=1 ./scripts/demo.sh`, open `/docs`, use `POST /documents` with name `podcasts` and content `# Podcasts\n\nPodcast episodes can be played at speeds from 0.5x to 3x.`, then ask "What playback speeds do podcasts support?" in the page.

## Configuration

All settings live in [`app/config.py`](app/config.py) and can be overridden with environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `RAG_CHAT_MODEL` | `qwen3:8b` | Chat model (try `qwen3:1.7b` to compare with the class model) |
| `RAG_EMBED_MODEL` | `embeddinggemma` | Embedding model |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama address |
| `RAG_TOP_K` | `4` | Chunks retrieved per question |
| `RAG_MIN_SCORE` | `0.30` | Best match needed before the LLM is called |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `500` / `80` | Chunking, in characters |
| `RAG_MAX_ANSWER_TOKENS` | `400` | Maximum answer length |
| `RAG_KEEP_ALIVE` | `30m` | How long Ollama keeps the model loaded |
| `RAG_ALLOW_UPLOADS` | off | Enable `POST /documents` |

## Before presenting (rehearsal checklist)

1. Run `./scripts/demo.sh` and open the printed phone address on your phone. The first time, macOS may ask whether Python can accept incoming connections: choose **Allow**.
2. If the phone cannot connect, the classroom Wi-Fi probably isolates devices from each other. Turn on your phone's hotspot, connect the laptop to it, and run the script again (it prints the new address).
3. Ask one question before the audience arrives so the model is loaded (the script's startup already does a warm up).
4. Close other heavy apps; `qwen3:8b` needs about 5 GB of memory.
5. If anything looks wrong with the index, stop the server, delete `chroma_db/`, and start again; it rebuilds from `knowledge/`.

## Project layout

```
app/
  config.py         all settings, env overridable
  embeddings.py     Ollama embeddings with embeddinggemma's prefixes
  vector_store.py   parsing, chunking, Chroma index, search
  rag.py            prompt, generation, sources, warm up
  errors.py         Ollama failures → 503 / 504 JSON errors
  question_log.py   JSON Lines question log
  main.py           FastAPI app and endpoints
web/index.html      the web client (self contained, works offline)
knowledge/          the six Resonance help documents
scripts/demo.sh     LAN demo launcher
docs/scope/         build plan
docs/specs/         design decisions (0001 to 0005)
design.md           visual design of the page
```

## What we learned

- **Write help documents as prose, not mixed lists.** A bullet list of seven device types embedded poorly: the Apple Watch line scored 0.31 against "Does Resonance work on Apple Watch?", while a prose sentence naming the topic scored 0.72. Rewriting that section as short paragraphs fixed retrieval.
- **A relevance cutoff beats prompt only refusals.** Measured scores were about 0.5 to 0.6 for real questions and 0.1 to 0.15 for off topic ones, so a 0.30 cutoff declines off topic questions instantly and the small model never gets the chance to answer from general knowledge.
- **Ask for a paragraph.** Allowing bullet lists made `qwen3:8b` answer in terse one line bullets that dropped details like "up to 6 accounts"; asking for one short paragraph fixed both.
