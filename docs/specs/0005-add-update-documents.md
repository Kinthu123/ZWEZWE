# 0005. Add or update documents: guarded JSON upsert

**Date**: 2026-11-01
**Status**: In Progress

## Summary

`POST /documents` lets you add a new Resonance help document, or replace an existing one, by sending its name and text as JSON; it is saved to `knowledge/` and searchable immediately. Because anyone on the classroom Wi-Fi can reach the API, the endpoint is switched off unless you start the server with `RAG_ALLOW_UPLOADS=1`. Nothing changes on disk or in the index unless the whole operation succeeds.

## Context

The tutorial includes a document write endpoint, and showing "add a new policy, then ask about it" is a strong demo moment. But spec 0001 runs the demo server on the LAN with no auth, so an open write endpoint lets anyone in the room rewrite or poison the knowledge base during your presentation.

Spec 0002 already provides `replace_document(source, text)`, which validates the name, parses the title, embeds, and swaps that document's chunks under the lock, but deliberately does not write the file. If the file is not written, the next restart (which rebuilds from `knowledge/`) silently drops the document; if the file is written but indexing fails, disk and index disagree until the next restart.

## Requirements

**User stories**:
- As the presenter, I want to add a new help document from `/docs` and immediately ask about it, to show the knowledge base is live.
- As the presenter, I want the endpoint off by default so nobody else on the Wi-Fi can change my documents.

**Acceptance criteria**:
- **AC-1**: With uploads enabled, `POST /documents` with a valid new `name` and `content` returns 200 with `created: true`, writes `knowledge/<name>.txt` with exactly that content, reports its `title` and `chunks`, and a following `/ask` can cite it.
- **AC-2**: Posting an existing name returns `created: false`, replaces the file, and leaves none of that document's old chunks beyond its new length; other documents are untouched.
- **AC-3**: With uploads disabled (the default), the endpoint returns 403 with "Document uploads are turned off. Start the server with RAG_ALLOW_UPLOADS=1 to enable them." and changes nothing.
- **AC-4**: A `name` not matching `^[A-Za-z0-9_-]{1,64}$` (for example `../x`, `a b`, 65 characters), `content` that is empty, over 20,000 characters, or has no text after its first (title) line returns 422 and changes nothing.
- **AC-5**: If Ollama is unreachable or times out, the endpoint returns 503 or 504, the file on disk and the index are unchanged, and no temporary file is left behind.
- **AC-6**: A document added this way is still indexed after a server restart.

## Options considered

### Option 1: Always open (the tutorial)

The endpoint is available whenever the server runs.

**Pros**:
- Nothing to configure.

**Cons**:
- Anyone on the classroom network can overwrite or add documents mid demo.

### Option 2: Off unless an environment flag is set (recommended)

`RAG_ALLOW_UPLOADS=1` turns the endpoint on; otherwise it returns 403.

**Pros**:
- Safe by default; you enable it only when you want to show it.
- No secret to type in Swagger.

**Cons**:
- When enabled, it is still open to anyone on the network for that run.

### Option 3: Shared token header

Require `X-Admin-Token` to match a configured secret.

**Pros**:
- Can stay on while still protected.

**Cons**:
- Another secret to manage and type during a demo; overkill for a local class project.

## Decision

**Chosen option**: Option 2: Off unless an environment flag is set.

Add `POST /documents` taking JSON `{name, content}`, enabled only when `RAG_ALLOW_UPLOADS=1`, which upserts the document into the index and then atomically saves it to `knowledge/<name>.txt`.

## Rationale

The real risk is a stranger changing your documents during the presentation, and a default off flag removes it with one line of config and no secret to fumble on stage. JSON `{name, content}` matches the tutorial and is the quickest thing to fill in on the `/docs` page. Writing to a temporary file first, indexing, and only then renaming means a failure at any step leaves the previous state intact, and the final file guarantees the document survives restarts (spec 0002 rebuilds from disk).

## Feature design

**Data model sketch**: no new store. The document is a file `knowledge/<name>.txt` (source of truth) plus its chunks in the spec 0002 collection, with `source = name`. The first line of `content` is the title (a leading `#` is optional), per spec 0002 parsing.

| Model | Field | Type | Rules |
|---|---|---|---|
| `DocumentRequest` | `name` | str | `^[A-Za-z0-9_-]{1,64}$` |
| `DocumentRequest` | `content` | str | 1 to `MAX_DOC_CHARS` (20,000); needs text after its first line |
| `DocumentResponse` | `name`, `title`, `chunks`, `created`, `latency_ms` | str, str, int, bool, int | |

**Flow** (`POST /documents`, plain `def`):
1. If `ALLOW_UPLOADS` is false → 403 (AC-3).
2. Validate the body (Pydantic) → 422 (AC-4). Start a timer; `created = not path.exists()`.
3. Write `content` to `knowledge/.<name>.<random>.tmp` (hidden, so `load_documents` ignores it).
4. `chunks = vector_store.replace_document(name, content)` inside `ollama_errors()`; a `ValueError` (no body text) → 422. On any failure, delete the temp file and re raise (AC-5).
5. `os.replace(temp, knowledge/<name>.txt)` (atomic on the same folder) (AC-1, AC-6).
6. Return `name`, the parsed `title`, `chunks`, `created`, `latency_ms`.

**API surface**:
| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/documents` | POST | `name`: str (req), `content`: str (req) | `name`, `title`, `chunks`, `created`, `latency_ms` | enabled only by `RAG_ALLOW_UPLOADS=1` | 403 disabled, 422 invalid, 503 Ollama down, 504 timeout |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| upsert | enabled or not | `config.ALLOW_UPLOADS` from env `RAG_ALLOW_UPLOADS` (`"1"`, `"true"`, `"yes"` mean on) |
| upsert | file path | `config.KNOWLEDGE_DIR / f"{name}.txt"` |
| upsert | `created` | whether that path existed before step 3 |
| upsert | `title` | `vector_store.parse_document(content)[0]`, falling back to `name` |
| upsert | `chunks` | return value of `vector_store.replace_document` |
| upsert | size limit | `config.MAX_DOC_CHARS` (20,000, env `RAG_MAX_DOC_CHARS`) |
| upsert | `latency_ms` | timer around steps 3 to 5 |

**Key invariants**:
- The file and the index change together or not at all (except a crash between steps 4 and 5, which the next restart repairs by rebuilding from disk).
- A document name can never escape `knowledge/` (strict pattern, no dots or slashes).

**Security model**: Write access is off by default. When enabled, anyone who can reach the server can add or replace documents for that run; this is accepted for a local classroom demo and should only be turned on while you show it. Content is plain text, stored and later shown only as escaped text (spec 0003).

**Configuration required**:
- `RAG_ALLOW_UPLOADS`: enable `POST /documents` (default off).
- `RAG_MAX_DOC_CHARS`: maximum document length (default `20000`).

**Critical test scenarios**:
- Happy path: enable uploads, post `podcasts` with a title and a fact ("Podcast episodes can be played at speeds from 0.5x to 3x"), get `created: true`; `/ask` "What playback speeds do podcasts support?" cites Podcasts, verifies **AC-1**.
- Replace: post `podcasts` again with shorter content → `created: false`, fewer chunks, no stale ids, verifies **AC-2**.
- Disabled: default server → 403 and no file, verifies **AC-3**.
- Invalid: `../x`, `a b`, empty content, title only, 20,001 characters → 422, verifies **AC-4**.
- Failure: Ollama unreachable → 503, no file, no `.tmp` left, verifies **AC-5**.
- Restart: restart the server and ask again; still cited, verifies **AC-6**.

## Build plan

1. [ ] Add `ALLOW_UPLOADS` and `MAX_DOC_CHARS` to `app/config.py`, satisfies **AC-3**, **AC-4**
2. [ ] `DocumentRequest` and `DocumentResponse` models and `POST /documents` in `app/main.py` (flag check, temp write, index, atomic rename, cleanup), satisfies **AC-1**, **AC-2**, **AC-4**, **AC-5**, **AC-6**
3. [ ] Run the critical scenarios against the live server, satisfies **AC-1** to **AC-6**

## Consequences

**Positive**:
- A live "add a policy, then ask about it" demo with no restart.
- Safe by default on a shared network.

**Negative / tradeoffs**:
- Enabling it opens writes to everyone on the network for that run.
- No delete endpoint; remove a document by deleting its file and restarting.

**Neutral**:
- Uploaded documents live in `knowledge/` like the originals, so they appear in git status; commit or delete them as you like.
