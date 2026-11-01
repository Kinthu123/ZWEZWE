# 0003. Web client design: warm vinyl single page help desk

**Date**: 2026-11-01
**Status**: Accepted

## Summary

The Resonance help desk is one self contained web page with hand written CSS, no internet needed. It has a warm, music flavoured look (off white background, deep plum accent, coral highlight) and a single column layout: a brand header, a big question box with one click example questions, an answer card with source chips and response time, and a short footer. It is built to read well on a classroom projector and on the instructor's phone, and it never breaks its look if the Wi-Fi blocks outside sites.

## Context

The page is what the demo video shows and what the instructor touches in class, so it has to be obvious to use with no instructions, readable from the back of a room, and usable on a phone that joins over the LAN. The classroom network may be slow or block outside sites, so anything loaded from the internet (CSS frameworks, fonts, icons) is a risk to the demo.

The page talks to the API from the same address (spec 0001: FastAPI serves `/`), so it can call `/ask` with relative URLs and needs no CORS. Answers come from `qwen3:8b`, which often replies with light markdown (bold, bullet lists), and take several seconds, so the page must show progress, block double submits, and explain failures (model server down, timeout) in plain words instead of failing silently.

The assignment rewards showing that answers come from the documents, so sources need to be visible and the retrieval visibly "working". No `design.md` exists yet and no design reference was given; the engineer asked for a proposed direction.

## Requirements

**User stories**:
- As the instructor, I want to type or tap a question and get a clear answer with its sources so that I can judge the system in seconds.
- As the presenter, I want the model name and response time shown so that I can talk about the larger model and its speed.
- As a phone user on the classroom Wi-Fi, I want the page to look and work the same as on the laptop.

**Acceptance criteria**:
- **AC-1**: Loading `/` makes no requests to any other host; the page is fully styled with the network to outside sites blocked (all CSS, the logo, and the script are inline in `web/index.html`).
- **AC-2**: The page shows, top to bottom: brand header (logo mark, "Resonance Help Desk", one line subtitle), question card (labelled textarea, character counter, Ask button, "Try one" example chips), answer card (hidden until the first question), footer.
- **AC-3**: Enter submits, Shift+Enter inserts a new line; the counter shows `n / 500`; input is capped at 500 characters; Ask is disabled while the trimmed question is empty.
- **AC-4**: Clicking an example chip puts its question in the box and submits it.
- **AC-5**: While a request is in flight, Ask and the chips are disabled, the answer card shows a loading line ("Searching the help docs and writing an answer…") with an animated indicator, and a second submit is impossible; the question stays in the box afterwards.
- **AC-6**: The answer is rendered with safe mini markdown: text is HTML escaped first, then only paragraphs, `**bold**`, and `- ` or `* ` bullet lists become markup; any HTML in the answer appears as literal text.
- **AC-7**: Under the answer, sources show as chips `"<title> · <NN>%"`, one per document, best score first; with no sources the row reads "No matching help documents".
- **AC-8**: Under the sources, a meta line shows `"<model> · <seconds, one decimal> s"`.
- **AC-9**: Errors show inside the answer card in plain words: 422 → "Please enter a question between 1 and 500 characters."; 503 → "The model server isn't running. Start Ollama and try again."; 504 → "That took too long. Try again, or ask a shorter question."; network failure → "Can't reach the Resonance server. Check that it's running."; anything else → "Something went wrong (error <status>)." Controls re-enable after any error.
- **AC-10**: At 360 px wide there is no horizontal scrolling and everything stays usable; all controls work by keyboard with a visible focus ring; the answer region is announced to screen readers (`aria-live="polite"`); text and controls meet WCAG AA contrast.

## Options considered

### Option 1: Bootstrap from a CDN (the tutorial page)

The class page: Bootstrap 5 linked from a CDN, default components, plain text answer.

**Pros**:
- Familiar; little CSS to write.

**Cons**:
- Loses all styling if the classroom network blocks or slows the CDN, the exact moment it matters.
- Looks like every other class project; asterisks from markdown show literally.

### Option 2: One self contained page, hand written CSS tokens, warm vinyl direction (recommended)

Everything inline in `web/index.html`: CSS custom properties for the palette, the system font stack, an inline SVG logo, and a small script for the ask flow and safe mini markdown.

**Pros**:
- Works fully offline and loads instantly over the LAN.
- A distinct, presentable look tuned for projector and phone.

**Cons**:
- You write and own about 200 lines of CSS instead of borrowing components.

### Option 3: Chat style thread

Message bubbles stacking each question and answer.

**Pros**:
- Feels like a modern assistant.

**Cons**:
- Implies follow up memory, which is deferred, so it promises something the system does not do.
- Long threads push sources out of view during a demo.

## Decision

**Chosen option**: Option 2: One self contained page, hand written CSS tokens, warm vinyl direction.

Build `web/index.html` as a single self contained single column page in the warm vinyl direction below, with all CSS, the SVG logo, and the script inline, calling `POST /ask` with a relative URL and rendering the response contract below.

## Rationale

The demo runs on a network you do not control, and Option 1 is the one design that can visibly break because of it, so self contained wins before looks even enter. A single column keeps the question, answer, and sources in one vertical read on both a projector and a phone, while the chat thread (Option 3) suggests memory the system does not have and scrolls the evidence away.

The warm vinyl palette is high contrast on projectors (dark plum ink on off white, rather than a dark theme that washes out) and gives the fictional brand some character. Safe mini markdown keeps `qwen3:8b`'s formatting readable while escaping first makes injected HTML impossible, matching the tutorial's XSS caution. Source chips with match percentages turn retrieval into something the audience can see.

## Feature design

**Design direction** (recorded by `/develop` into `design.md`; token values live in the page's CSS):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FBF7F2` | page background (warm off white) |
| `--surface` | `#FFFFFF` | cards |
| `--ink` | `#2A2233` | body text |
| `--muted` | `#6B6170` | secondary text, counter, meta line |
| `--border` | `#E9E1D8` | card and input borders |
| `--accent` | `#5B2A86` | plum: Ask button, links, focus ring, chip text |
| `--accent-soft` | `#F1EAF7` | chip background, loading tint |
| `--highlight` | `#FF6B5A` | coral: logo groove and small decorative accents only, never text |
| `--danger` | `#B42318` | error text and border |

- Type: system font stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`), base 17 px, line height 1.6; title 28 px semibold; no web fonts.
- Shape: cards 16 px radius with a soft shadow; chips fully rounded; 8 px spacing scale (8, 16, 24, 32).
- Layout: content max width 760 px, centered, 16 px side gutter on small screens.
- Logo: inline SVG vinyl record (plum disc, coral label ring), 40 px.
- Motion: only the loading indicator (three pulsing dots); respects `prefers-reduced-motion`.
- Light theme only.

**Page composition** (top to bottom): header (logo, title, subtitle "Answers from Resonance's help documents") → question card (label "Ask a question about Resonance", textarea 3 rows, counter right aligned, Ask button, "Try one" chips) → answer card (loading line, or error, or answer body + sources row + meta line) → footer ("Resonance is a fictional service made for a class project · API docs" linking `/docs`).

**Example chips** (one per document):
- "How much is the Family plan?"
- "How many devices can I download music on?"
- "How long can I stay on the Student plan?"
- "Does Resonance work on Apple Watch?"
- "When do artists get paid?"
- "Can I get a refund on the yearly plan?"

**Component inventory** (all net new, plain HTML and CSS): header, card, textarea with counter, primary button (default, hover, focus, disabled), chip button (example chips) and chip label (sources), loading indicator, error message, answer body (paragraphs, bold, lists).

**Assets**: none external. The only image is the inline SVG logo.

**API surface consumed** (the contract the ask and answer spec must provide):

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/ask` | POST | JSON `question`: str (req, 1 to 500 chars) | `answer`: str, `sources`: list of `{source, title, score}` best first, `model`: str, `latency_ms`: int | none | 422 invalid, 503 Ollama down, 504 timeout |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| ask | question sent | textarea value, trimmed |
| ask | character counter | textarea value length, cap `maxlength="500"` (matches the API's 500 limit) |
| render | answer body | `answer` from the `/ask` response, through safe mini markdown |
| render | source chip title | `sources[].title` (spec 0002 metadata `title`) |
| render | source chip percent | `Math.round(sources[].score * 100)` (score is 0 to 1, spec 0002) |
| render | source order and dedupe | response order (best first); the page also drops repeat `source` values defensively |
| render | meta line model | `model` from the response |
| render | meta line seconds | `(latency_ms / 1000).toFixed(1)` from the response |
| error | message text | HTTP status mapped by AC-9; network failure from a rejected `fetch` |
| chips | example questions | the fixed list above, in the page |

**Key invariants**:
- No `innerHTML` with unescaped text: answer text is escaped before the mini markdown transforms; titles, model, and errors are set with `textContent`.
- Exactly one request in flight at a time.
- The page uses only relative URLs, so it works on any host and port it was served from.

**Security model**: Public page, no accounts, no cookies, no stored data. The only untrusted input rendered is the model's answer and document titles, both escaped (AC-6). Nothing is sent anywhere except `POST /ask` on the same origin.

**Configuration required**: none.

**Critical test scenarios**:
- Happy path: tap "How much is the Family plan?" → loading line → answer mentions $17.99, chips show "Plans and Pricing · NN%", meta shows `qwen3:8b · N.N s`, verifies **AC-4**, **AC-5**, **AC-7**, **AC-8**.
- Offline styling: block outside network (or open DevTools network log) and reload; zero requests to other hosts and the page is fully styled, verifies **AC-1**.
- Injection: an answer containing `<img src=x onerror=alert(1)>` and `**bold**` shows the tag as text and bold as bold, verifies **AC-6**.
- Failure case: stop Ollama and ask; the 503 message appears and Ask re-enables, verifies **AC-9**.
- Phone: 360 px viewport, keyboard only flow (Tab to box, type, Enter, Tab to chips), verifies **AC-3**, **AC-10**.

## Build plan

Tracer Bullet: the page shell and its states are built against the `/ask` contract now; the ask and answer slice then makes the endpoint real, and the page works end to end with no further UI change.

1. [x] Write `design.md` (art direction, tokens table, components, do and don't) from this spec, satisfies **AC-1**, **AC-10**
2. [x] `web/index.html` structure: header, question card with label, counter, Ask, chips, hidden answer card with `aria-live`, footer, inline SVG logo, satisfies **AC-1**, **AC-2**
3. [x] Inline CSS: tokens, layout, card, button, chip, loading dots, error, responsive rules, focus ring, reduced motion, satisfies **AC-1**, **AC-2**, **AC-10**
4. [x] Inline script: input handling (Enter, Shift+Enter, counter, empty guard), chip submit, single request lock, `fetch('/ask')`, satisfies **AC-3**, **AC-4**, **AC-5**
5. [x] Inline script: safe mini markdown, source chips (dedupe, percent), meta line, error mapping, satisfies **AC-6**, **AC-7**, **AC-8**, **AC-9**

## Consequences

**Positive**:
- The page cannot lose its styling to a bad network, and it loads instantly over the LAN.
- One file to read, present, and grade.
- The `/ask` response contract is now fixed, so the ask and answer spec has a concrete target.

**Negative / tradeoffs**:
- Hand written CSS and mini markdown are code you maintain; richer markdown (tables, links) is not rendered.
- No dark mode.
- Until the ask and answer slice lands, the page shows the 404 error path when you press Ask.

**Neutral**:
- `design.md` becomes the visual source of truth for any later UI (none is planned).

## Follow-up

- [ ] For the ask and answer spec: honor the `/ask` response contract above, including `sources` deduplicated by `source` and sorted best first, and `latency_ms` measured server side.
