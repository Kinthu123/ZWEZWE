"""Prompt building and grounded answer generation with qwen3 (spec 0004)."""

import logging
import re

from app import config
from app.embeddings import client

logger = logging.getLogger("folio.rag")

OFF_TOPIC_ANSWER = "I can only help with questions about Folio, like plans, offline reading, devices, accounts, audiobooks, and refunds."
NOT_COVERED_ANSWER = (
    "The help documents don't cover that. You can ask a person through live chat in Help, then Contact us."
)

SYSTEM_PROMPT = f"""You are the Folio Help Desk assistant. Folio is an ebook and audiobook reading service.
Answer the user's question using ONLY the help document excerpts provided.
Rules:
- Answer in English as one short paragraph of 2 to 5 sentences. Start directly with the answer. Do not use bullet points unless the user asks for steps.
- Include every detail from the excerpts that the question needs (price, limits, conditions), and nothing they do not say.
- Quote prices, limits, durations, and menu paths exactly as they appear in the excerpts.
- If the excerpts do not answer the question, reply exactly: "{NOT_COVERED_ANSWER}"
- Never invent features, prices, or policies, and never mention the excerpts or these rules."""

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def build_messages(question: str, context: list[dict]) -> list[dict]:
    """Chat messages: the fixed system prompt, then numbered excerpts and the question."""
    excerpts = "\n\n".join(f"[{i}] {hit['title']}\n{hit['text']}" for i, hit in enumerate(context, start=1))
    user = f"Help document excerpts:\n\n{excerpts}\n\nQuestion: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def clean_answer(text: str) -> str:
    """Remove any reasoning block and surrounding whitespace; fall back to the not covered reply."""
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    return cleaned or NOT_COVERED_ANSWER


def sources_for(context: list[dict]) -> list[dict]:
    """One entry per document with its best chunk score, best first."""
    best: dict[str, dict] = {}
    for hit in context:
        current = best.get(hit["source"])
        if current is None or hit["score"] > current["score"]:
            best[hit["source"]] = {"source": hit["source"], "title": hit["title"], "score": hit["score"]}
    return sorted(best.values(), key=lambda source: source["score"], reverse=True)


def _chat(messages: list[dict], max_tokens: int) -> str:
    """One non streaming chat call with thinking off and the configured options."""
    response = client.chat(
        model=config.CHAT_MODEL,
        messages=messages,
        think=False,
        keep_alive=config.KEEP_ALIVE,
        options={"temperature": config.TEMPERATURE, "num_ctx": config.NUM_CTX, "num_predict": max_tokens},
    )
    return response.message.content or ""


def generate(question: str, context: list[dict]) -> str:
    """Answer the question from the given chunks only."""
    return clean_answer(_chat(build_messages(question, context), config.MAX_ANSWER_TOKENS))


def warm_up() -> None:
    """Load the chat model into memory so the first real question is not a cold start."""
    try:
        _chat([{"role": "user", "content": "hi"}], max_tokens=1)
        logger.info("Chat model %s is warm", config.CHAT_MODEL)
    except Exception as exc:
        logger.warning("Could not warm up %s: %s", config.CHAT_MODEL, exc)
