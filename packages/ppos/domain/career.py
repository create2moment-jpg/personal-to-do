"""Career intelligence: expectations, evidence links and explainable matching.

Principles: only *accepted* facts count as evidence; links are made or
confirmed by the user; coverage is a hypothesis, never a promotion verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

EVIDENCE_KINDS = ("achievement", "responsibility", "competency", "strength")

_STOPWORDS = (
    "a an and are as at be by for from has have in into is it its of on or that the their this "
    "to was were with within across end per who what when where which while will can should "
    "must more most other others them they our we you your his her he she not no do does done "
    "also than then very"
)
_STOP = frozenset(_STOPWORDS.split())
_LEVEL_RE = re.compile(r"\b(L\d{1,2}|E\d{1,2}|IC\d{1,2}|P\d{1,2}|Level\s*\d{1,2})\b", re.IGNORECASE)


@dataclass
class Expectation:
    id: str
    level: str
    text: str
    created_at: datetime
    updated_at: datetime
    competency: str | None = None
    source_fact_id: str | None = None
    position: float = 0.0


@dataclass(frozen=True)
class EvidenceLink:
    id: str
    expectation_id: str
    fact_id: str
    origin: str  # user | suggestion (confirmed by the user)
    created_at: datetime
    score: float | None = None
    note: str = ""


def level_from_section(section: str | None) -> str | None:
    """'L5 — Senior Software Engineer' → 'L5'; returns None when no level marker exists."""
    if not section:
        return None
    m = _LEVEL_RE.search(section)
    return m.group(1).upper().replace(" ", "") if m else None


_IRREGULAR = {
    "led": "lead", "drove": "drive", "built": "build", "wrote": "write", "ran": "run",
    "grew": "grow", "taught": "teach", "made": "make", "set": "set", "owned": "own",
}  # fmt: skip


def stem(word: str) -> str:
    """A deliberately small, predictable stemmer: leads/led/leading → lead."""
    w = _IRREGULAR.get(word, word)
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in _STOP]


def tokens(text: str) -> set[str]:
    return {stem(w) for w in _words(text)}


@dataclass(frozen=True)
class Match:
    fact_id: str
    score: float
    shared: tuple[str, ...]  # the words that explain the match


def match_score(expectation_text: str, evidence_text: str) -> Match | None:
    """Explainable overlap score: share of the expectation's terms present in the evidence.

    ``shared`` lists the expectation's own words that matched, so the reason for a
    suggestion can be shown to the user as-is.
    """
    words = _words(expectation_text)
    exp, ev = {stem(w) for w in words}, tokens(evidence_text)
    if not exp or not ev:
        return None
    common = exp & ev
    if not common:
        return None
    shown: dict[str, str] = {}
    for w in words:
        if stem(w) in common:
            shown.setdefault(stem(w), w)
    return Match("", round(len(common) / len(exp), 3), tuple(sorted(shown.values())))


SEMANTIC_FLOOR = 0.2  # below this nothing counts as "similar in meaning"
SEMANTIC_NEAR_BEST = 0.8  # keep only candidates close to the best one
SEMANTIC_MARGIN = 0.1  # …and clearly above the typical similarity in the pool


def meaning_matches(sims: dict[str, float]) -> dict[str, float]:
    """Pick the candidates that stand out by meaning, independent of the model's scale.

    Embedding models differ widely in their baseline similarity, so an absolute
    threshold is unreliable. A candidate is kept when it is near the best match and,
    for pools of four or more, clearly above the median of the pool.
    """
    if not sims:
        return {}
    best = max(sims.values())
    cut = max(SEMANTIC_FLOOR, best * SEMANTIC_NEAR_BEST)
    if len(sims) >= 4:
        ordered = sorted(sims.values())
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
        cut = max(cut, median + SEMANTIC_MARGIN)
    return {k: round(v, 3) for k, v in sims.items() if v >= cut}
