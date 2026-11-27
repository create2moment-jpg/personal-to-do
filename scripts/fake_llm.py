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
    def do_GET(self) -> None:
        if self.path.rstrip("/").endswith("/v1/models"):
            self._json({"object": "list", "data": [{"id": "fake-llm", "object": "model"}]})
        else:
            self._json({"models": [{"name": "fake-llm"}]})

    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        user = next(
            (m["content"] for m in payload.get("messages", []) if m.get("role") == "user"), ""
        )
        if "Reply with exactly: OK" in user:
            answer = "OK"
        elif "review for" in user and "Each line is one item with its ID" in user:
            answer = review_draft(user)
        elif 'Allowed "kind" values' in user:
            answer = extract_facts(user)
        else:
            answer = improve(user)
        model = payload.get("model") or "fake-llm"
        message = {"role": "assistant", "content": answer}
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
