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
