"""Validation and clean-up of model output (small local models add noise)."""

from __future__ import annotations

import re

from ppos.ai.provider import AIOutputError

_PREAMBLE = re.compile(
    r"^(here(?:'s| is) (?:the |an |your )?(?:improved|revised|rewritten)[^:\n]*:\s*)", re.IGNORECASE
)


def clean_improved(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^<think>.*?</think>\s*", "", t, flags=re.DOTALL)  # reasoning models
    t = _PREAMBLE.sub("", t)
    fenced = re.fullmatch(r"```[\w-]*\n(.*)\n```", t, flags=re.DOTALL)
    if fenced:
        t = fenced.group(1)
    t = t.strip().strip("<>").strip()
    if t.startswith('"') and t.endswith('"') and t.count('"') == 2:
        t = t[1:-1]
    if not t:
        raise AIOutputError(
            "the local model returned an empty answer — try again or pick another style"
        )
    return t


_BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
_QUOTED = re.compile(r"[\"“]([^\"”]{3,80})[\"”]")


def parse_change_notes(text: str, original: str, improved: str, limit: int = 5) -> list[str]:
    """Bullet points explaining a rewrite, kept only when they stay grounded.

    A note that quotes words found in neither version is dropped: the explanation
    must describe the actual change, not an imagined one.
    """
    t = re.sub(r"^<think>.*?</think>\s*", "", text.strip(), flags=re.DOTALL)
    both = f"{original}\n{improved}".lower()
    notes: list[str] = []
    for raw in t.splitlines():
        line = _BULLET.sub("", raw).strip().strip("*").strip()
        if not line or line.endswith(":") or len(line) > 240:
            continue
        if any(q.strip().lower() not in both for q in _QUOTED.findall(line)):
            continue
        notes.append(line)
        if len(notes) == limit:
            break
    if not notes:
        raise AIOutputError("the local model gave no usable explanation — try again")
    return notes
