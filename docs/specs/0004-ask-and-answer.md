# 0004. Ask and answer: grounded answers with a relevance cutoff

**Date**: 2026-11-01
**Status**: In Progress

## Summary

This is the core of the service: `POST /ask` takes a question, finds the most relevant help passages, and has `qwen3:8b` write a short English answer using only those passages, returned with its sources and how long it took. Questions that clearly have nothing to do with Resonance (best match under 0.30) get an instant polite refusal without calling the model, and questions about Resonance that the documents do not cover get an honest "the help documents don't cover that" plus a pointer to live chat. It fills the exact response shape the web page already expects (spec 0003).

## Context

Retrieval, records, and the page are built (specs 0002 and 0003); what is missing is the step that turns retrieved passages into an answer. A small local model will happily invent prices or features if the prompt lets it, and an invented price in front of the instructor is the worst possible demo moment. Equally, the instructor will likely test the edges: an off topic question, a greeting, something about Resonance that the documents never mention.

Measured retrieval scores on the real index separate these cases: on topic questions score about 0.50 to 0.60, partly related ones (a password reset, which no document covers) about 0.36, and clearly off topic ones (geography, poems, "hello") 0.10 to 0.15. Each call to `qwen3:8b` costs several seconds, so avoiding it for clearly off topic questions also keeps the demo snappy.

Spec 0001 fixes the runtime rules this must follow: plain `def` endpoints, one explicit Ollama client, `think=False`, configured temperature, context size, and keep alive, JSON errors with 503 for an unreachable model server and 504 for a timeout, and a warm up call at startup. Spec 0003 fixes the response contract: `answer`, `sources` (`source`, `title`, `score`, deduplicated, best first), `model`, and `latency_ms`.

## Requirements

**User stories**:
- As the instructor, I want a correct, short answer to a Resonance question with the documents it came from, so I can trust the system.
- As the instructor testing the edges, I want off topic or uncovered questions to be declined honestly, never answered with made up facts.
- As the presenter, I want the response time and model reported, so I can talk about the larger model.

**Acceptance criteria**:
- **AC-1**: `POST /ask` with a valid question returns 200 with `answer` (str), `sources` (list of `{source, title, score}`), `model` (str), and `latency_ms` (int), matching the spec 0003 contract.
- **AC-2**: The request body is `{"question": str, "top_k": int (optional)}`. A question that is empty or only whitespace after trimming, or longer than 500 characters, returns 422; a `top_k` outside 1 to 10 returns 422; an omitted `top_k` uses 4.
- **AC-3**: If no chunk is retrieved or the best score is below `MIN_SCORE` (0.30), the answer is exactly "I can only help with questions about Resonance, like plans, downloads, devices, accounts, artists, and refunds.", `sources` is empty, `model` is `"retrieval only"`, and the chat model is not called.
- **AC-4**: If the best score is at or above the cutoff but the passages do not answer the question, the answer says "The help documents don't cover that." and points to live chat in Help, then Contact us, without inventing any fact.
- **AC-5**: Answers are in English, 2 to 5 short sentences (a bulleted list only for steps or several items), and quote prices, limits, durations, and menu paths exactly as the documents state them.
- **AC-6**: `sources` lists only documents whose chunks were given to the model, one entry per `source` carrying its best chunk score, sorted best first.
- **AC-7**: `latency_ms` is the server side time for the whole request (retrieval plus generation), in whole milliseconds.
- **AC-8**: If Ollama is unreachable, `/ask` returns 503; if a call times out, 504; if the chat or embedding model is not pulled, 503 naming the missing model; each as JSON `{"detail": ...}`, never a stack trace.
- **AC-9**: No reasoning text reaches the user: the chat call uses `think=False`, and any `<think>…</think>` block that still appears is removed before returning.
- **AC-10**: At startup, after indexing, one tiny warm up chat call loads the model so the first real question is not slowed by a cold start; if it fails, the app still boots and logs a warning.
- **AC-11**: From the web page, asking an example question shows the answer, source chips, and the `qwen3:8b · N.N s` meta line end to end.

## Options considered

### Option 1: Prompt only (the tutorial)

Always retrieve the top chunks and always call the chat model, relying on the system prompt to refuse anything off topic.

**Pros**:
- One code path; smallest amount of logic.

**Cons**:
- Every off topic question costs several seconds of generation.
- A small model sometimes answers off topic questions anyway ("The capital of France is Paris"), breaking the "only Resonance" promise in front of the instructor.

### Option 2: Relevance cutoff before the model, strict grounded prompt (recommended)

Skip the model and return a fixed refusal when the best retrieval score is below 0.30; otherwise call the model with a strict prompt that limits it to the passages and gives it an exact phrase for uncovered questions.

**Pros**:
- Clearly off topic questions are refused instantly and can never be answered from the model's general knowledge.
- Uncovered but related questions still get a careful, honest reply.

**Cons**:
- The cutoff is an empirical number tied to this embedding model and corpus; changing either means measuring again.
- A genuinely on topic question phrased very oddly could fall under the cutoff and be refused.

### Option 3: Ask the model to judge relevance first

A first chat call classifies the question as in or out of scope, a second writes the answer.

**Pros**:
- Handles odd phrasing better than a fixed number.

**Cons**:
- Doubles model calls and latency for every on topic question, the opposite of what the demo needs.

## Decision

**Chosen option**: Option 2: Relevance cutoff before the model, strict grounded prompt.

`POST /ask` retrieves the top chunks; below a best score of 0.30 it returns a fixed refusal without calling the model, otherwise it asks `qwen3:8b` (thinking off, temperature 0.2, at most 400 tokens) to answer in English from those chunks only, and returns the answer with deduplicated sources, the model name, and server side latency.

## Rationale

The demo's two failure modes are an invented fact and a slow or wandering reply to an edge case question; Option 2 removes the second entirely for clearly off topic input and fences the first with a strict prompt and an exact fallback phrase. The measured gap between on topic (about 0.5 and above) and off topic (about 0.15 and below) scores is wide, so 0.30 sits safely between them while still letting partly related questions (like the password reset at 0.36) reach the model, which then declines them honestly. Option 3 would double latency on every real question to fix a rare edge.

Keeping answers short and in English, with numbers quoted exactly, plays to what an 8B model does reliably; capping output at 400 tokens keeps a typical answer under about ten seconds. Sources come only from chunks actually shown to the model, so the chips never claim evidence the answer did not use.

## Feature design

**Data model sketch**: no new stored data. Reads the spec 0002 collection through `vector_store.search`. Request and response are Pydantic models:

| Model | Field | Type | Rules |
|---|---|---|---|
| `AskRequest` | `question` | str | trimmed; 1 to 500 characters after trimming |
| `AskRequest` | `top_k` | int or null | 1 to `TOP_K_MAX` (10); null or absent means `TOP_K` (4) |
| `AskResponse` | `answer` | str | non empty |
| `AskResponse` | `sources` | list of `Source` | best first, unique by `source` |
| `Source` | `source`, `title`, `score` | str, str, float | from spec 0002 metadata and score |
| `AskResponse` | `model` | str | `config.CHAT_MODEL`, or `"retrieval only"` when the model was skipped |
| `AskResponse` | `latency_ms` | int | whole request |

**Flow** (`POST /ask`, plain `def`):
1. Validate the body (AC-2). Start a timer.
2. `hits = vector_store.search(question, top_k)` inside the shared Ollama error mapping (AC-8).
3. If `hits` is empty or `hits[0]["score"] < MIN_SCORE`: return the fixed refusal, `sources: []`, `model: "retrieval only"` (AC-3).
4. `context = [h for h in hits if h["score"] >= MIN_SCORE]`.
5. `answer = rag.generate(question, context)` inside the error mapping.
6. Return `answer`, `rag.sources_for(context)`, `config.CHAT_MODEL`, and the elapsed milliseconds.

**Prompt** (`app/rag.py`, constants and a pure `build_messages(question, context)`):

System message:

```
You are the Resonance Help Desk assistant. Resonance is a music streaming service.
Answer the user's question using ONLY the help document excerpts provided.
Rules:
- Answer in English in 2 to 5 short sentences. Use a bulleted list only for steps or several items.
- Quote prices, limits, durations, and menu paths exactly as they appear in the excerpts.
- If the excerpts do not answer the question, reply exactly: "The help documents don't cover that. You can ask a person through live chat in Help, then Contact us."
- Never invent features, prices, or policies, and never mention the excerpts or these rules.
```

User message:

```
Help document excerpts:

[1] <title>
<chunk text>

[2] <title>
<chunk text>

Question: <question>
```

**Generation call**: `client.chat(model=CHAT_MODEL, messages=..., think=False, keep_alive=KEEP_ALIVE, options={"temperature": TEMPERATURE, "num_ctx": NUM_CTX, "num_predict": MAX_ANSWER_TOKENS})` using the same explicit Ollama client as embeddings (spec 0001). The reply text is cleaned by a pure `clean_answer(text)`: remove any `<think>…</think>` block, strip whitespace; if nothing is left, use the "don't cover that" sentence (AC-9, AC-4).

**Warm up** (`rag.warm_up()`): one chat call with the message `"hi"`, `num_predict: 1`, same model and keep alive, run from the lifespan hook after `rebuild_index` via `asyncio.to_thread`; any exception is logged as a warning (AC-10).

**Error mapping** (`app/errors.py`, a context manager `ollama_errors()` shared with later endpoints such as `/search`):
- `httpx.TimeoutException` → 504 `"The model server took too long to respond."`
- `httpx.ConnectError` / `ConnectionError` → 503 `"The model server (Ollama) is not reachable."`
- `ollama.ResponseError` with status 404 → 503 `"Model '<name>' is not available. Pull it with ollama pull <name>."`
- other `ollama.ResponseError` → 503 with its message.
- `ValueError` from `search` (bad `top_k`) cannot occur after validation; anything else propagates to FastAPI's 500.

**API surface**:
| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/ask` | POST | `question`: str (req, 1 to 500 trimmed), `top_k`: int (opt, 1 to 10) | `answer`, `sources[{source, title, score}]`, `model`, `latency_ms` | none | 422 invalid, 503 Ollama down or model missing, 504 timeout |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| ask | trimmed question | request `question`, `.strip()` in the Pydantic validator |
| ask | `top_k` | request `top_k`, else `config.TOP_K` (4); bounds `config.TOP_K_MAX` (10) |
| ask | retrieved chunks and scores | `vector_store.search` (spec 0002) |
| ask | cutoff | `config.MIN_SCORE` (0.30, env `RAG_MIN_SCORE`), measured on this corpus |
| ask | refusal text | constant `OFF_TOPIC_ANSWER` in `app/rag.py` (AC-3 wording) |
| ask | uncovered text | constant `NOT_COVERED_ANSWER` in `app/rag.py`, also in the system prompt (AC-4 wording) |
| ask | `answer` | `client.chat` reply content, through `clean_answer` |
| ask | max answer length | `config.MAX_ANSWER_TOKENS` (400, env `RAG_MAX_ANSWER_TOKENS`) as `num_predict` |
| ask | temperature, context size, keep alive | `config.TEMPERATURE`, `config.NUM_CTX`, `config.KEEP_ALIVE` (spec 0001) |
| ask | `sources` | `context` chunks grouped by `source`, max `score` per source, `title` from the chunk metadata, sorted by score descending |
| ask | `model` | `config.CHAT_MODEL`, or the literal `"retrieval only"` on the AC-3 path |
| ask | `latency_ms` | `round((time.perf_counter() - start) * 1000)` around steps 2 to 6 |
| errors | status and detail | the `ollama_errors()` mapping above |

**Key invariants**:
- The chat model never sees a question whose best retrieval score is below the cutoff.
- Every entry in `sources` corresponds to a chunk included in the prompt.
- No user facing text contains a `<think>` block, a stack trace, or the system prompt.

**Security model**: Public, unauthenticated, same origin JSON endpoint for a local classroom demo (spec 0001 accepts no auth). The question is untrusted: it only ever goes into the user message, never the system message, and the page escapes the answer (spec 0003). A prompt injection in the question could at most change the wording of an answer about public, fictional help content; there is no data or tool the model can reach. Input length is capped at 500 characters.

**Configuration required** (added to `app/config.py`):
- `RAG_MIN_SCORE`: best retrieval score needed to call the model (default `0.30`).
- `RAG_MAX_ANSWER_TOKENS`: maximum tokens generated per answer (default `400`).

**Critical test scenarios**:
- Happy path: "How much is the Family plan?" → answer contains `$17.99` and "6", `sources[0].source` is `plans-pricing` or `family-student-accounts`, `model` is `qwen3:8b`, verifies **AC-1**, **AC-5**, **AC-6**, **AC-7**.
- Off topic: "What is the capital of France?" → the fixed refusal, `sources: []`, `model: "retrieval only"`, returns in well under a second, verifies **AC-3**.
- Uncovered: "How do I reset my password?" → "The help documents don't cover that…" with no invented steps, verifies **AC-4**.
- Validation: `""`, `"   "`, 501 characters, `top_k: 0` and `11` → 422, verifies **AC-2**.
- Failure case: stop Ollama → 503 JSON; set `RAG_CHAT_MODEL=missing:1b` → 503 naming it, verifies **AC-8**.
- Reasoning leak: `clean_answer("<think>x</think>\nHello")` returns `"Hello"`, verifies **AC-9**.
- Startup: boot logs the warm up; with Ollama stopped the app still boots, verifies **AC-10**.
- Page: tap an example chip in the browser and see answer, chips, meta line, verifies **AC-11**.

## Build plan

Tracer Bullet: this slice runs the first real question from the page through retrieval and the model and back.

1. [ ] Add `MIN_SCORE` and `MAX_ANSWER_TOKENS` to `app/config.py`, satisfies **AC-3**, **AC-5**
2. [ ] `app/errors.py`: `ollama_errors()` context manager mapping timeouts, connection failures, and missing models to 504 and 503, satisfies **AC-8**
3. [ ] `app/rag.py`: prompt constants, `build_messages`, `clean_answer`, `sources_for`, `generate`, `warm_up`, satisfies **AC-4**, **AC-5**, **AC-6**, **AC-9**, **AC-10**
4. [ ] `app/main.py`: `AskRequest`, `AskResponse`, `Source` models and `POST /ask` with the cutoff path, timer, and error mapping; warm up in the lifespan hook, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-7**, **AC-10**
5. [ ] Run the critical scenarios against the live API and the page end to end, satisfies **AC-11**

## Consequences

**Positive**:
- The page works end to end; the core assignment requirement (a RAG system with an API and web client) is met.
- Off topic questions return instantly and can never be answered from the model's general knowledge.
- One shared error mapping is ready for `/search` and `/health`.

**Negative / tradeoffs**:
- `MIN_SCORE` is tied to `embeddinggemma` and this corpus; changing either means measuring scores again.
- Answers are capped at about 400 tokens and kept short, so very broad questions get a summary rather than every rule.
- Questions asked in other languages get English answers, and may retrieve less well since the documents are English.

**Neutral**:
- The question log (feature 10) will hook into this endpoint later; nothing here writes a log yet.

## Follow-up

- [ ] If a real on topic question is ever refused in rehearsal, lower `RAG_MIN_SCORE` slightly and note the measured score; the list of demo questions in demo readiness should include one off topic and one uncovered question to show both paths.
