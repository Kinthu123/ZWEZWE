# Scope: Resonance Help Desk (RAG Q&A)

A local question answering system for **Resonance**, a fictional music streaming service. You ask a question in a web page, the system finds the right passages in Resonance's own help documents and a local LLM answers using only those passages, showing its sources. Built for a class assignment: at least six documents on different topics, a larger LLM than the class example, an API, and a web client that an instructor can try live.

**Build approach:** Tracer Bullet (get one real question flowing from the web page through retrieval and the LLM and back first, then thicken each part end to end).
**Workflow:** Alpha (after `/develop`, run `/check verify` on the real app). The project default level of rigor. `/architect` is the recommended first stop for a feature with a real decision, but skippable when you already know the build. Any feature can carry its own tag (e.g. `· Beta`) to do more or less.

_These are recommendations to keep your build orderly, not requirements. Skip anything that does not fit: if you already know how to build a feature, use `/develop` and skip `/architect`. You decide when a feature is `done`._

## At a glance

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | Stack & architecture | Foundation | done |
| 2 | Coding standards & tooling | Foundation | done |
| 3 | Knowledge record shape | Foundation | done |
| 4 | Resonance knowledge documents | Foundation | done |
| 5 | Web client design | Foundation | in-progress |
| 6 | Ask and answer | Slice 1 | planned |
| 7 | Search without the LLM | Slice 2 | planned |
| 8 | Health check | Slice 3 | planned |
| 9 | Add or update documents | Slice 4 | planned |
| 10 | Question log | Slice 5 | planned |
| 11 | Demo readiness | Slice 6 | planned |

## Foundations

### 1. Stack & architecture · done
Record the stack the tutorial implies, plus the assignment's bigger chat model, and scaffold a runnable app so every slice builds on real structure.
**Done when:** the stack (language, web framework, embedding model, chat model, vector store) is recorded in a spec and an empty app boots locally with its docs page reachable.
- [x] Decide the stack (spec): `/architect stack & architecture`
- [x] Scaffold from the decision: `/develop stack & architecture`
- [x] Verify it: skipped (boot plus `/` and `/docs` checked during `/develop`)
Spec [0001](../specs/0001-stack-architecture.md) · code in `app/`, `web/`

### 2. Coding standards & tooling · done
Capture conventions and tooling from the real scaffolded project, then install them.
**Done when:** root `AGENTS.md` reflects the real stack and commands, and the chosen lint or format tooling runs clean.
- [x] Capture conventions + tooling choices: `/audit`
- [x] Install the tooling: `/develop tooling`
code in `AGENTS.md`, `pyproject.toml`, `requirements-dev.txt`

### 3. Knowledge record shape · done
How a document becomes searchable records: chunk size and overlap, the id scheme, the metadata each chunk keeps, the similarity measure, and how many chunks are retrieved by default.
**Done when:** every chunk can be traced back to its source document and position, and indexing again updates records rather than duplicating them.
- [x] Design it (spec): `/architect knowledge record shape`
- [x] Build it: `/develop knowledge record shape`
   - [x] Config and embeddings with prefixes (AC-3, AC-6)
   - [x] Parsing, chunking, and file rules (AC-1, AC-2, AC-8)
   - [x] Index lifecycle: rebuild, status, startup hook (AC-3, AC-4, AC-5)
   - [x] Search and replace under the lock (AC-6, AC-7, AC-9)
- [x] Verify it: all 9 ACs exercised by a scenario run during `/develop` (22 checks passed)
Spec [0002](../specs/0002-knowledge-record-shape.md) · code in `app/embeddings.py`, `app/vector_store.py`

### 4. Resonance knowledge documents · done
At least six plain text help documents for Resonance, each on a clearly different topic (for example plans and pricing, offline downloads, family and student accounts, devices and playback, artist uploads and royalties, refunds and cancellation). Fictional, consistent with each other, and full of specific facts a demo question can hit.
**Done when:** six or more documents exist in `knowledge/`, each on a distinct topic, with concrete details (prices, limits, steps) that only these documents can answer, each with a title on its first line and blank lines between paragraphs (format from spec 0002).
- [x] Write them: `/develop resonance knowledge documents`
code in `knowledge/` (6 documents)

### 5. Web client design · in-progress
The look and layout of the single Q&A page: question box, answer area, source list, loading and error states. It is what the instructor and the demo video see first.
**Done when:** `design.md` covers layout, type, color, and the loading, empty, and error states, and the page is usable on a laptop and a phone.
- [x] Design it (spec): `/architect web client design`
- [x] Build it: `/develop web client design`
   - [x] `design.md` with the warm vinyl tokens and components (AC-1, AC-10)
   - [x] Page structure and inline CSS, responsive and accessible (AC-1, AC-2, AC-10)
   - [x] Ask flow script: input, chips, lock, mini markdown, sources, meta, errors (AC-3 to AC-9)
- [ ] Verify it: `/check verify web client design` (needs `/ask` from feature 6)
Spec [0003](../specs/0003-web-client-design.md) · code in `web/index.html`, `design.md`

## Slice 1: Ask and answer

### 6. Ask and answer · needs a decision
The core loop and the walking skeleton: documents are indexed at startup, a user types a question in the web page, the API retrieves the best chunks, the chat model answers using only them, and the page shows the answer with its sources.
**Done when:** a question about Resonance gets a grounded answer with its source documents shown in the page; a question the documents cannot answer gets an honest "I don't know" rather than an invented fact; the response reports how long it took.
- [ ] Design it (spec): `/architect ask and answer`

## Slice 2: Search without the LLM

### 7. Search without the LLM
Return the most relevant chunks for a query without calling the chat model, to inspect and debug retrieval.
**Done when:** a search returns the top chunks with their source and score, and the number of results is adjustable within safe limits.
- [ ] Build it: `/develop search without the llm`

## Slice 3: Health check

### 8. Health check
A quick status check showing whether the model server is reachable and how many chunks are indexed.
**Done when:** the check reports healthy with a chunk count when everything runs, and reports clearly when the model server is down.
- [ ] Build it: `/develop health check`

## Slice 4: Add or update documents

### 9. Add or update documents · needs a decision
Add a new help document or replace an existing one through the API, and have it searchable right away.
**Done when:** a posted document is saved and indexed again, an answer can cite it immediately, and unsafe document names (path tricks, odd characters) are rejected.
- [ ] Design it (spec): `/architect add or update documents`

## Slice 5: Question log

### 10. Question log
Record every question asked, with time, sources used, and latency, so you can show usage during the presentation.
**Done when:** each question appends one line to a log file with its timestamp, question, sources, and latency, and a logging failure never breaks an answer.
- [ ] Build it: `/develop question log`

## Slice 6: Demo readiness

### 11. Demo readiness
Make the system easy to run and to try in class: one clear start command, a short README, and a set of demo questions that show off each document.
**Done when:** a fresh clone starts with the documented commands, the instructor can open the page from another device on the same network (rehearsed from a phone, with a hotspot fallback, from spec 0001), and a list of demo questions covers every document.
- [ ] Build it: `/develop demo readiness`

## Deferred
Out of scope for the current build pass, kept so the plan stays honest.
- **Streaming answers**: show the answer word by word as it is generated · needs a decision
- **Conversation memory**: follow up questions that remember earlier ones · needs a decision
- **Container packaging**: run the API and model server as containers · needs a decision

## Legend

**The decision box.** Every feature carries exactly one, the sub task whose label ends with `(spec)`. Its wording varies (`Design it (spec)` normally, `Decide the stack (spec)` on Stack & architecture), so skills locate it by that `(spec)` suffix, never by an exact label. Every other box is an execution box and `/architect` never ticks one.

**Feature lifecycle**: the scope updates as a feature moves; each row is what it shows and who sets it:

| State | Set by | The feature shows |
|---|---|---|
| `planned` · needs a decision | `/scope` | one box: `Design it (spec): /architect <feature>` |
| `in-progress` (designed) | **`/architect` at spec capture** | `Design it` ticked; spec linked; `Build it: /develop <feature>` + **2 to 5 milestones**; the tier's closing boxes (`Verify it` Alpha+, `Test it` Beta+, `Review it` + `Document it` GA); any surfaced follow up enrolled |
| `in-progress` (building) | `/develop` | milestone sub boxes tick one by one; code pointer filled |
| `in-progress` (verified) | `/check verify` | `Build it` + milestones ticked; `Verify it` ticked |
| `done` | **you, when you decide it is** (any skill sets it when you say so); `/sync` reconciles | boxes you ran ticked, skipped ones marked skipped; the tier's last stage (`Prototype` → after `/develop`; `Alpha` → after `/check verify`; `Beta`/`GA` → after `/test`) is the suggested point to call it done; `/sync` captures conventions |

- **Next step** = the first unticked box (always a command or a tracked milestone).
- **needs a decision** = run `/architect` first; otherwise straight to `/develop` (or `/audit` for standards & tooling). The tag drops once the spec is captured.
- **Atomic build tasks live in the spec's `## Build plan`, not here**: the scope carries only the milestone rollup.
- **Status** `planned` → `in-progress` → `done`, plus `existing` (pre workflow) and `dropped` (de scoped, kept for history).
- **Approach tag** beside a heading (e.g. `· Facade`) overrides the project default for that feature; no tag = inherits it.
- **Workflow tier tag** beside a heading (e.g. `· Beta`, `· Prototype`) sets that one feature's rigor above or below the project default; no tag inherits the default. It decides the feature's check boxes and each skill's next suggestion.
- **Workflow** (header line) is the project default, what runs after `/develop`: **Prototype** = nothing (trust develop's own build time self check); **Alpha** = `/check verify`; **Beta** = `/check verify` then `/test`; **GA** = adds a fresh model `/check review` then `/document`. A feature built on an unratified decision (an `Assumed` spec) stays flagged, but that never blocks `done`.
- **Pointer line** (`spec <n> · code in <path>`): the spec link added by `/architect`, the code path by `/develop`.
