# 0002. Knowledge record shape: paragraph chunks rebuilt at startup

**Date**: 2026-11-01
**Status**: In Progress

## Summary

This decides how Resonance's help documents become searchable records. Each `.txt` file is split into chunks of about 500 characters along paragraph lines, each chunk is turned into an embedding (a list of numbers capturing its meaning) by `embeddinggemma`, and the chunks are stored in one Chroma collection with their source file, title, and position. The collection is brought in line with `knowledge/` every time the app starts, so it never holds stale text, and a failed rebuild never wipes a good index. Every later feature (ask, search, health, add documents) reads and writes records in exactly this shape.

## Context

The service answers only from Resonance's own help documents, so retrieval quality decides answer quality. A chunk that cuts a sentence in half (for example "Family costs $16." split from "per month for up to 6 members") produces wrong or partial answers, and in a live demo a wrong price is the most visible failure there is.

Each answer must also cite its sources so the instructor can see where it came from, which means every chunk has to trace back to its document and position, ideally with a human friendly title. Documents will be edited while you prepare the demo, and the add or update documents feature will replace documents at runtime, so the store must never keep chunks from an older version of a file or from a deleted file.

The knowledge base is tiny (six or more short documents, likely under a hundred chunks). Embedding all of it takes seconds on the M4. `embeddinggemma` produces best results when queries and documents are embedded with different task prefixes, and its vectors suit cosine similarity, while Chroma defaults to a different distance (L2) unless told otherwise. Spec 0001 fixes that the app always supplies its own vectors, that Chroma runs as one embedded client, and that endpoints run in a thread pool, so a search and a document replacement can run at the same time.

## Requirements

**User stories**:
- As someone asking about Resonance, I want answers built from whole, intact passages so that prices, limits, and steps are never cut off.
- As the presenter, I want every retrieved passage to show which document it came from so that the instructor can check the answer.
- As the person preparing the demo, I want edits to `knowledge/` to show up on the next start, with nothing stale left behind.

**Acceptance criteria**:
- **AC-1**: Every valid document's body (the text after its title line) is split into chunks that break on paragraph boundaries where possible, then line, then sentence, then word boundaries, never mid word; no chunk exceeds `CHUNK_SIZE + CHUNK_OVERLAP` characters (580 by default), and no chunk except a document's only chunk is shorter than 100 characters.
- **AC-2**: Each chunk after the first in a document begins with up to 80 characters taken from the end of the previous chunk's own text (not its overlap), starting on a word boundary; if that tail has no space to cut at, there is no overlap.
- **AC-3**: Every stored record has id `"{source}:{chunk}"`, the chunk text (without title or prefix) as its document, and metadata `source` (str), `title` (str), and `chunk` (int); given any record you can find its file and position.
- **AC-4**: After a successful startup rebuild the collection contains exactly the chunks of the current files: an edited file has no old chunks left, a deleted file has none at all, and an empty `knowledge/` leaves the collection empty.
- **AC-5**: If embedding fails during a rebuild (for example Ollama is down), the stored collection is left exactly as it was, the app still boots, and `index_status()` reports the failure.
- **AC-6**: `search(query, top_k)` returns up to `top_k` records (default 4, allowed 1 to 10), best first, each with its text, source, title, chunk, and a score in [0, 1]; an empty collection returns an empty list; a `top_k` outside 1 to 10 raises `ValueError`.
- **AC-7**: `replace_document(source, text)` updates only that document's records: its new chunks are present, any chunks beyond its new length are gone, and every other document is untouched; an invalid name or empty body raises `ValueError`.
- **AC-8**: Files that are not top level, do not fully match `^[A-Za-z0-9_-]+\.txt$`, are not valid UTF-8, or have no body text after the title are skipped with a logged warning, never indexed and never fatal.
- **AC-9**: A search running at the same time as `replace_document` never errors and sees either the old or the new chunks of that document, never a missing collection.

## Options considered

### Option 1: Fixed character slices, upsert by id (the tutorial)

Slice each file every 500 characters with 80 characters of overlap, and upsert records by id on every start.

**Pros**:
- Smallest amount of code; matches the class article line for line.

**Cons**:
- Cuts sentences and prices in half, which hurts both retrieval and the answer.
- When a document gets shorter, its higher numbered chunks linger forever; deleted files never leave the index.

### Option 2: Paragraph aware chunks, full rebuild at startup (recommended)

Pack whole paragraphs into chunks up to about 500 characters with a short word aligned overlap, embed with `embeddinggemma`'s task prefixes, and at every start embed the whole corpus, then upsert it and delete any ids that no longer exist.

**Pros**:
- Chunks hold complete facts, so retrieval and answers are more accurate.
- The index always matches `knowledge/` exactly, and there is never an empty window where searches would find nothing.

**Cons**:
- Every start spends a few seconds embedding everything again.
- More chunking code than fixed slicing, plus a lock around writes.

### Option 3: Paragraph chunks, incremental upsert with content hashes

Same chunking, but store a hash per file and only embed files whose hash changed; delete chunks of removed files.

**Pros**:
- Fastest restarts once the knowledge base grows.

**Cons**:
- More code and more edge cases (hash bookkeeping, partial failures) to save seconds on a six document corpus.

### Option 4: One chunk per section

Split on headings, one section per record.

**Pros**:
- Very clean citations when documents are well structured.

**Cons**:
- Chunk sizes vary wildly; a long section dilutes its embedding and floods the prompt.

## Decision

**Chosen option**: Option 2: Paragraph aware chunks, full rebuild at startup.

Split each document body into paragraph aware chunks of about 500 characters with up to 80 characters of overlap, embed them with `embeddinggemma`'s document prefix, store them in one cosine Chroma collection named `resonance_help` with `source`, `title`, and `chunk` metadata, and at every startup embed the whole corpus first, then upsert it and delete vanished ids under a lock, keeping the index untouched if embedding fails.

## Rationale

The demo's riskiest moment is a wrong fact, and fixed slicing (Option 1) creates wrong facts by cutting sentences, so chunking on paragraphs is worth its extra code. A full rebuild is the simplest way to make the index provably match the files: with under a hundred chunks it costs seconds, so the incremental bookkeeping in Option 3 buys nothing you would notice.

Upserting and then deleting only vanished ids, instead of dropping and recreating the collection, means there is never a moment with an empty or missing collection: a crash midway leaves a mix of old and new chunks that the next start repairs, and a search running in parallel never hits a deleted collection. Embedding everything before touching Chroma keeps AC-5 true, so a stopped Ollama never changes a good index. Recovery from a failed rebuild is simply restarting once Ollama is up; retrying silently inside a user's search would add hidden state and a surprise delay.

Using `embeddinggemma`'s separate query and document prefixes and cosine distance follows how the model was trained; skipping either quietly lowers relevance. A default `top_k` of 4 (one above the tutorial) lets a question that spans two documents, such as a plan price plus its refund rule, reach both, while still keeping prompts short for an 8B model.

## Feature design

**Data model sketch**:

One Chroma collection, `resonance_help`, opened with `get_or_create_collection` with cosine distance and `embedding_function=None` (vectors always come from the app). If an existing collection reports a distance other than cosine (for example one left by the tutorial), it is deleted and recreated once at startup, before traffic.

| Field | Type | Required | Source / rule |
|---|---|---|---|
| `id` | str | yes, unique | `"{source}:{chunk}"`, e.g. `refunds-cancellation:2`; `:` can never appear in a source |
| `document` | str | yes | the chunk text, overlap included, without title line or prefix |
| `embedding` | list of float | yes | `embeddinggemma` of `"title: {title} \| text: {document}"` |
| `metadata.source` | str | yes | file name without `.txt`, matching `^[A-Za-z0-9_-]+$` |
| `metadata.title` | str | yes | first non empty line of the file with leading `#` and spaces stripped; if that leaves nothing, the source name |
| `metadata.chunk` | int | yes | 0 based position within its document, contiguous |

Relationship: one document file has many chunks (1:N), joined by `metadata.source`. There is no separate documents table; the files in `knowledge/` are the source of truth and the collection is a rebuildable index of them.

**Document parsing** (`parse_document(text) -> (title, body)`, pure):
- Normalize line endings to `\n`, strip a leading BOM, replace tabs with spaces.
- The first non empty line is the title line; everything after it is the body. The title line is never part of any chunk.

**Chunking algorithm** (`chunk_text(body) -> list[str]`, pure):
1. Split the body into paragraphs on blank lines; collapse runs of spaces inside each; strip; drop empty ones.
2. Any paragraph longer than `CHUNK_SIZE` is broken into pieces: first on single newlines (list items), then any piece still too long on sentence ends (`. `, `? `, `! ` followed by a capital letter or digit, which avoids most decimals like `$9.99`), then any piece still too long on spaces. Pieces are greedily repacked up to `CHUNK_SIZE`.
3. Greedily pack paragraphs and pieces in order (paragraphs joined by a blank line, pieces of one paragraph by a space) into chunk bodies of at most `CHUNK_SIZE` characters.
4. If the last chunk body is under `CHUNK_MIN` (100) characters and there is a previous one, merge it into the previous one.
5. Overlap: each chunk after the first is prefixed with the tail of the previous chunk's own body, at most `CHUNK_OVERLAP` characters, trimmed forward to just after the first space in that tail; no space means no overlap. Final chunk = overlap + `"\n"` + body when there is an overlap. Maximum length is therefore `CHUNK_SIZE + CHUNK_OVERLAP + 1`.

**Concurrency**: one module level `threading.Lock` in `app/vector_store.py`. All Chroma writes (`rebuild_index`, `replace_document`) and the Chroma query inside `search` take it. Embedding calls happen outside the lock, so a slow embed never blocks other requests' Chroma work.

**Index status** (module level, written only under the lock): `{"chunks": int, "last_rebuild_ok": bool | None, "last_rebuild_at": ISO time str | None, "error": str | None}`. `None` values mean no rebuild has run yet.

**State transitions**: none per record. Startup: open or create the collection → `load_documents` → embed all chunks (outside the lock) → (success) lock, upsert all new records, delete ids present before but not in the new set, update status ok → ready. Embed failure: no Chroma change, status records the error, app runs on the existing index until restart.

**Internal interface** (Python functions, no HTTP; the endpoints that call them are other features):

| Function | Module | Inputs | Outputs | Key errors |
|---|---|---|---|---|
| `embed_documents(items)` | `app/embeddings.py` | list of (title, text) | list of vectors, same order and length | Ollama unreachable or timeout (raised to caller); length mismatch raises `RuntimeError` |
| `embed_query(text)` | `app/embeddings.py` | query string | one vector | same |
| `parse_document(text)` | `app/vector_store.py` | raw file text | (title, body) | none (pure) |
| `chunk_text(body)` | `app/vector_store.py` | document body | list of chunk strings | none (pure) |
| `load_documents()` | `app/vector_store.py` | none (reads `config.KNOWLEDGE_DIR`, non recursive) | list of (source, title, body) sorted by source | skips invalid files with a warning (AC-8) |
| `rebuild_index()` | `app/vector_store.py` | none | `index_status()` dict | never raises; failures land in the status (AC-5) |
| `replace_document(source, text)` | `app/vector_store.py` | source name, full file text | number of chunks for that source | `ValueError` for bad name or empty body; Ollama errors raised, index unchanged |
| `search(query, top_k=config.TOP_K)` | `app/vector_store.py` | query, `top_k` | list of `{text, source, title, chunk, score}` best first | `ValueError` for `top_k` outside 1 to `TOP_K_MAX`; Ollama errors raised |
| `index_status()` | `app/vector_store.py` | none | copy of the status dict with a fresh `chunks` count | none |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| parsing | `title` | first non empty line, `#` stripped; fallback the source name |
| parsing | body | file text after the title line |
| chunking | chunk boundaries | `config.CHUNK_SIZE` (500), `config.CHUNK_OVERLAP` (80), `config.CHUNK_MIN` (100), and the split order above |
| indexing | `source` | file name stem from `config.KNOWLEDGE_DIR` |
| indexing | `chunk` | position in `chunk_text` output |
| indexing | `id` | derived: `f"{source}:{chunk}"` |
| indexing | document vector | `config.EMBED_MODEL` on `f"title: {title} \| text: {chunk}"`, in batches of `config.EMBED_BATCH` (32) |
| indexing | ids to delete | ids from `collection.get(include=[])` (or `where={"source": source}` for one document) minus the new id set |
| search | query vector | `config.EMBED_MODEL` on `f"task: search result \| query: {query}"` |
| search | `top_k` | caller input, default `config.TOP_K` (4), allowed 1 to `config.TOP_K_MAX` (10) |
| search | result count | `n_results = min(top_k, collection.count())`; 0 means return `[]` without querying |
| search | `score` | derived: `round(min(1.0, max(0.0, 1 - distance)), 3)` from Chroma's cosine distances |
| search | order | Chroma's nearest first ordering |
| status / health | `chunks`, `last_rebuild_ok`, `last_rebuild_at`, `error` | `collection.count()` and the module level status set by `rebuild_index` |

**Key invariants**:
- After a successful rebuild the collection contains only chunks of files currently in `knowledge/`, plus any document added later through `replace_document` (which feature 9 also writes to disk).
- Ids are unique; within one document chunk numbers are contiguous from 0.
- The query and document prefixes are always applied; stored text never contains a prefix or the title line.
- Chroma is never written without holding the lock, and never written before all embeddings for that write succeeded.
- The collection object is opened once and never deleted while the app serves traffic.

**Security model**: The knowledge is fictional public help content with no personal data and no compliance scope. Only the app process reads and writes the collection. Source names are restricted to `^[A-Za-z0-9_-]+$` and files are read only from the top level of `knowledge/`, so a source name can never become a path (`../`), and `replace_document` validates the name itself rather than trusting its caller.

**Configuration required** (added to `app/config.py`, env overridable per spec 0001):
- `RAG_CHUNK_SIZE`: target maximum chunk body length in characters (default `500`).
- `RAG_CHUNK_OVERLAP`: overlap carried into the next chunk (default `80`).
- `RAG_CHUNK_MIN`: a last chunk shorter than this merges into the previous one (default `100`).
- `RAG_EMBED_BATCH`: texts per embedding call (default `32`).
- `RAG_TOP_K`: default number of chunks retrieved (default `4`).
- `RAG_TOP_K_MAX`: upper bound callers may request (default `10`).
- `RAG_COLLECTION`: collection name (default `resonance_help`).

**Critical test scenarios**:
- Happy path: start with the sample documents; `index_status()` shows `last_rebuild_ok: true` and chunks above zero; `search("how much is the family plan")` returns the plans document first, verifies **AC-3**, **AC-4**, **AC-6**.
- Chunk integrity: a body with a 1,200 character paragraph and a bullet list becomes chunks under 581 characters that end on line, sentence, or word boundaries, start with a word aligned overlap, and none (except a lone chunk) is under 100 characters; the title line appears in no chunk, verifies **AC-1**, **AC-2**.
- Stale state: shorten a document from 5 chunks to 2 and restart; ids `:2` to `:4` for that source are gone; delete a file and restart; it has no records; empty `knowledge/` and restart; count is 0, verifies **AC-4**.
- Failure case: stop Ollama and restart the app; it boots, logs a warning, `index_status()` shows the error, and the count is unchanged, verifies **AC-5**.
- Replace: `replace_document("refunds-cancellation", shorter_text)` leaves other sources' counts unchanged and removes that source's extra chunks; `replace_document("../x", "...")` and an empty body raise `ValueError`, verifies **AC-7**.
- Concurrency: run searches in a loop while calling `replace_document` repeatedly; no search errors, verifies **AC-9**.
- Bad input: `bad name.txt`, a non UTF-8 file, a title only `blank.txt`, and a `sub/doc.txt` are all skipped with warnings; `search(q, top_k=0)` raises `ValueError`; an empty collection returns `[]`, verifies **AC-6**, **AC-8**.

## Build plan

Tracer Bullet: this foundation is built thin but complete, so the ask and answer slice can plug straight into it.

1. [x] Add `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_MIN`, `EMBED_BATCH`, `TOP_K`, `TOP_K_MAX`, `COLLECTION` to `app/config.py`, satisfies **AC-1**, **AC-6**
2. [x] `app/embeddings.py`: one explicit Ollama `Client` from config; `embed_documents` (document prefix, batches of `EMBED_BATCH`, length check) and `embed_query` (query prefix) via `client.embed`, satisfies **AC-3**, **AC-6**
3. [x] `parse_document` and `chunk_text` in `app/vector_store.py`: title split, paragraph packing, line, sentence, and word fallback, tail merge, word aligned overlap, satisfies **AC-1**, **AC-2**
4. [x] `load_documents`: non recursive, full name match, UTF-8 read, warn and skip invalid files, satisfies **AC-3**, **AC-8**
5. [x] Module level `PersistentClient`, cosine `get_or_create_collection` with the metric check, the lock, the status dict, `rebuild_index` (embed all, then upsert and delete vanished ids) and `index_status`, satisfies **AC-3**, **AC-4**, **AC-5**
6. [x] `search` (validate `top_k`, embed outside the lock, query inside it with `n_results` capped, clamp scores) and `replace_document` (validate, embed, then upsert and delete that source's vanished ids under the lock), satisfies **AC-6**, **AC-7**, **AC-9**
7. [x] Call `rebuild_index` from the FastAPI `lifespan` hook and log the resulting status, satisfies **AC-4**, **AC-5**

## Consequences

**Positive**:
- The index always mirrors the files after a successful start, so "did my edit take?" is answered by restarting.
- Chunks hold whole facts, and every result carries a friendly title for citations.
- Later features only call `search`, `replace_document`, and `index_status`; none of them touch Chroma directly.

**Negative / tradeoffs**:
- Every start re-embeds the whole corpus (a few seconds now, longer if the corpus grew to hundreds of documents; revisit with Option 3 then).
- If Ollama is down at startup, the app serves the last good index until you restart it with Ollama running; there is no automatic retry.
- A document added at runtime must also be written to `knowledge/` (feature 9), otherwise the next restart drops it.
- The lock serializes Chroma calls; harmless at classroom traffic, a bottleneck only under real load.

**Neutral**:
- Documents should be written with a title on the first line and blank lines between paragraphs; feature 4 follows this format.
- The stored text includes the overlap, so adjacent snippets shown to the user may repeat a few words, and one document can fill several of the top results.

## Follow-up

- [ ] For the ask and answer spec: `embeddinggemma` cosine scores tend to cluster around 0.3 to 0.7, so any minimum relevance threshold for refusing off topic questions must be calibrated by trying real questions, not guessed.
- [ ] For the ask and answer spec: deduplicate the cited sources by `source`, since one document can supply several of the top chunks.
