#!/usr/bin/env python3
"""Deterministic stand-in for a local Ollama server (tests and demos only).

Implements Ollama's /api/tags and /api/chat, and the OpenAI-compatible
/v1/models and /v1/chat/completions (llama.cpp server, vLLM, LM Studio).
The "improved" prompt restructures the original into Goal / Context / Ask so
the UI flow can be exercised without a real model. Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def improve(user_message: str) -> str:
    m = re.search(r"<<<\n(.*)\n>>>", user_message, re.DOTALL)
    original = (m.group(1) if m else user_message).strip()
    first = original.split("\n")[0].rstrip(".")
    return (
        f"Goal: {first[:1].upper() + first[1:]}.\n"
        "Context: [language/framework], [relevant files or functions].\n"
        "Constraints: keep behaviour unchanged; small, reviewable steps.\n"
        "Output: the changed code plus a short explanation of each step."
    )


def explain_changes(user_message: str) -> str:
    """Two grounded notes and one that quotes words from neither text (must be dropped)."""
    return (
        "Here is what changed:\n"
        "- Split the request into Goal, Context, Constraints and Output sections.\n"
        '- Added "Context:" placeholders so you can name the files instead of the model guessing.\n'
        '- Promised "a 300 percent speed-up" for the code.\n'
        "- Asked for a short explanation of each step."
    )


def extract_facts(user_message: str) -> str:
    """Return one grounded fact (first sentence, verbatim) and one ungrounded one."""
    m = re.search(r"<<<\n(.*)\n>>>", user_message, re.DOTALL)
    passage = (m.group(1) if m else "").strip()
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", " ".join(passage.split())) if len(s) > 12]
    if not sentences:
        return "[]"
    first = sentences[0]
    kind = "development_area" if re.search(r"delegate|improve|grow", first, re.I) else "achievement"
    if (
        re.search(r"\bleads?\b|owns?|sets technical direction", first, re.I)
        and "level" in user_message.lower()
    ):
        kind = "level_expectation"
    return json.dumps(
        [
            {"kind": kind, "statement": first[:120], "quote": first, "confidence": 0.82},
            # deliberately ungrounded — the app must drop it
            {
                "kind": "achievement",
                "statement": "Won a company award",
                "quote": "won the 2026 company award",
                "confidence": 0.9,
            },
        ]
    )


SYNONYMS = {"coach": "mentor", "coached": "mentor", "coaching": "mentor", "mentored": "mentor",
            "mentoring": "mentor", "mentors": "mentor", "retrieval": "search",
            "searching": "search"}  # fmt: skip
STOPWORDS = {"the", "and", "her", "his", "their", "other", "through", "two", "for", "with",
             "was", "that", "this", "first", "our"}  # fmt: skip


def embed(text: str, dim: int = 512) -> list[float]:
    """Deterministic bag-of-words vector; a few synonyms share a bucket so 'meaning' works."""
    import hashlib

    vec = [0.0] * dim
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        if word in STOPWORDS:
            continue
        word = SYNONYMS.get(word, word)
        vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dim] += 1.0
    return vec


def ask_answer(user_message: str) -> str:
    """Answer with the first source's first sentence and cite it; also cite a missing source."""
    m = re.search(r"^\[1\] \(\w+\) (.+)\n(.+)$", user_message, re.MULTILINE)
    if not m:
        return "I couldn't find that in your records."
    first = re.split(r"(?<=[.!?])\s", m.group(2))[0][:200]
    return f"From your records: {first} [1]"


def capture_line(user_message: str) -> str:
    """Very small rule-based stand-in for the model."""
    m = re.search(r"<<<\n(.*)\n>>>", user_message, re.DOTALL)
    text = (m.group(1) if m else "").strip()
    tokens = []
    rules = (
        (r"\btomorrow\b", "@tomorrow"),
        (r"\bhalf an hour\b|\b30 minutes\b", "~30m"),
        (r"\ban hour\b", "~1h"),
        (r"\burgent\b|\basap\b", "!1"),
    )
    for pattern, token in rules:
        if re.search(pattern, text, re.IGNORECASE):
            tokens.append(token)
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^(please\s+)?(remind me to|i need to|i have to|don't forget to)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(it )?takes\b|,", " ", text, flags=re.IGNORECASE)
    title = " ".join(text.split()).rstrip(".")
    return " ".join([title[:1].upper() + title[1:], *tokens])


def rewrite_note(user_message: str) -> str:
    """Drop filler words and capitalise lines — deterministic, adds nothing."""
    m = re.search(r"<<<\n(.*)\n>>>", user_message, re.DOTALL)
    text = m.group(1) if m else ""
    text = re.sub(r"\b(really|basically|just|very)\s+", "", text, flags=re.IGNORECASE)
    return "\n".join(line[:1].upper() + line[1:] for line in text.splitlines())


def plan_answer(user_message: str) -> str:
    """Pick the first two task ids offered, plus one invented id (must be dropped)."""
    ids = re.findall(r"^([0-9a-f]{32}) \|", user_message, re.MULTILINE)
    top = [{"id": i, "why": "due soon and high priority"} for i in ids[:2]]
    top.append({"id": "not-a-real-task", "why": "invented"})
    return json.dumps({"top": top, "note": "Front-load the deep work before meetings."})


def review_draft(user_message: str) -> str:
    """Cite the first items verbatim; add one bullet that invents a number (must be dropped)."""
    items = re.findall(r"^\[([A-Z]\d+)\] (.+)$", user_message, re.MULTILINE)
    by_prefix: dict[str, list[tuple[str, str]]] = {}
    for item_id, text in items:
        by_prefix.setdefault(item_id[0], []).append((item_id, text))

    def bullet(prefix: str) -> list[str]:
        return [f"{text} [{item_id}]" for item_id, text in by_prefix.get(prefix, [])[:2]]

    return json.dumps(
        {
            "highlights": bullet("S")
            + bullet("G")
            + ["Was promoted to principal engineer with 300 percent impact [S1]"],
            "challenges": bullet("M")[:1] + bullet("B"),
            "learnings": bullet("L") or ["No new learnings recorded"],
            "next_focus": bullet("G")[:1],
        }
    )


class Handler(BaseHTTPRequestHandler):
    def _embeddings(self, payload: dict[str, object]) -> None:
        inputs = payload.get("input") or []
        texts = [inputs] if isinstance(inputs, str) else list(inputs)  # type: ignore[arg-type]
        data = [
            {"object": "embedding", "index": i, "embedding": embed(str(t))}
            for i, t in enumerate(texts)
        ]
        self._json({"object": "list", "model": payload.get("model", "fake-embed"), "data": data})

    def do_GET(self) -> None:
        if self.path.rstrip("/").endswith("/v1/models"):
            self._json({"object": "list", "data": [{"id": "fake-llm", "object": "model"}]})
        else:
            self._json({"models": [{"name": "fake-llm"}]})

    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        if self.path.rstrip("/").endswith("/embeddings"):
            return self._embeddings(payload)
        user = next(
            (m["content"] for m in payload.get("messages", []) if m.get("role") == "user"), ""
        )
        if "Reply with exactly: OK" in user:
            answer = "OK"
        elif "review for" in user and "Each line is one item with its ID" in user:
            answer = review_draft(user)
        elif user.startswith("Today is ") and "Sources:" in user:
            answer = ask_answer(user)
        elif user.startswith("Convert my note into ONE capture line"):
            answer = capture_line(user)
        elif user.startswith("Explain the changes between"):
            answer = explain_changes(user)
        elif user.startswith("Rewrite my note text"):
            answer = rewrite_note(user)
        elif user.startswith("Plan my day"):
            answer = plan_answer(user)
        elif 'Allowed "kind" values' in user:
            answer = extract_facts(user)
        else:
            answer = improve(user)
        model = payload.get("model") or "fake-llm"
        message = {"role": "assistant", "content": answer}
        if payload.get("stream") and self.path.rstrip("/").endswith("/chat/completions"):
            return self._stream(answer, str(model))
        if self.path.rstrip("/").endswith("/chat/completions"):
            self._json(
                {
                    "object": "chat.completion",
                    "model": model,
                    "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                }
            )
        else:
            self._json({"model": model, "message": message})

    def _stream(self, answer: str, model: str) -> None:
        """Server-sent events in small word chunks, like llama.cpp / vLLM."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        pieces = re.findall(r"\S+\s*|\s+", answer)
        first = {"choices": [{"index": 0, "delta": {"role": "assistant"}}], "model": model}
        self.wfile.write(f"data: {json.dumps(first)}\n\n".encode())
        for piece in pieces:
            event = {"choices": [{"index": 0, "delta": {"content": piece}}], "model": model}
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.close_connection = True

    def _json(self, data: dict[str, object]) -> None:
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11999
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
