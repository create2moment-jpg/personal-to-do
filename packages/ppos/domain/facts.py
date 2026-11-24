"""Facts extracted from documents — always with provenance and a verbatim quote."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

FACT_KINDS = (
    "responsibility",
    "achievement",
    "competency",
    "strength",
    "development_area",
    "goal",
    "level_expectation",
)
MAX_FACTS_PER_CHUNK = 12


@dataclass
class Fact:
    id: str
    document_id: str
    kind: str
    statement: str
    quote: str
    confidence: float
    model: str
    prompt_template: str
    created_at: datetime
    updated_at: datetime
    chunk_id: str | None = None
    run_id: str | None = None
    page: int | None = None
    section: str | None = None
    epistemic: str = "document_claim"
    status: str = "proposed"
    extractor_version: str | None = None
    note: str = ""


@dataclass
class FactRun:
    id: str
    document_id: str
    status: str
    started_at: datetime
    model: str | None = None
    prompt_template: str | None = None
    chunks_total: int = 0
    chunks_done: int = 0
    facts_found: int = 0
    facts_dropped: int = 0
    error: str | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class CandidateFact:
    kind: str
    statement: str
    quote: str
    confidence: float


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(s.split()).lower()


def is_grounded(quote: str, passage: str) -> bool:
    """The quote must occur verbatim (modulo whitespace/case/curly quotes) in the passage."""
    q = _norm(quote).strip(" .\"'")
    return len(q) >= 8 and q in _norm(passage)


def parse_candidates(raw: str) -> list[CandidateFact]:
    """Tolerant JSON parsing for small local models; invalid items are skipped."""
    text = raw.strip()
    text = re.sub(r"^<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data: Any = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: list[CandidateFact] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip().lower().replace(" ", "_")
        statement = " ".join(str(item.get("statement", "")).split())[:400]
        quote = " ".join(str(item.get("quote", "")).split())[:600]
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        if kind in FACT_KINDS and statement and quote:
            out.append(CandidateFact(kind, statement, quote, min(max(conf, 0.0), 1.0)))
        if len(out) >= MAX_FACTS_PER_CHUNK:
            break
    return out
