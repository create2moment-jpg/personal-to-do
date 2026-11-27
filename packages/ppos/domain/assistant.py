"""Assistant: retrieval over your own records, rank fusion, and answer checks."""

from __future__ import annotations

import json
import math
import re
from array import array
from dataclasses import dataclass, field

RRF_K = 60  # reciprocal-rank fusion constant (Cormack et al.)

_QUESTION_TEXT = (
    "a an and are as at be by for from has have in into is it its of on or that the this to was "
    "were with what which who whom whose when where why how did do does done my me i we our you "
    "your about any some all can could should would will tell show give find list summarise "
    "summarize decide decided say said there their them they than then"
)
_QUESTION_WORDS = frozenset(_QUESTION_TEXT.split())


def keyword_terms(question: str) -> list[str]:
    """The words worth matching literally: drop question words and very short tokens."""
    words = [w.strip(".") for w in re.findall(r"[\w#@.+-]{2,}", question.lower())]
    out = [w for w in words if len(w) > 1 and w not in _QUESTION_WORDS]
    return list(dict.fromkeys(out))[:8]


@dataclass
class Source:
    """One retrieved passage, numbered for citation in an answer."""

    kind: str  # note | page | chunk | task
    id: str
    title: str
    text: str
    link: str  # view/arg the UI can open, e.g. "notes/<id>"
    n: int = 0  # citation number, assigned when the prompt is built
    via: list[str] = field(default_factory=list)  # "keyword" / "meaning"


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse ranked id lists; an item ranked high in either list rises."""
    score: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            score[key] = score.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score.items(), key=lambda kv: -kv[1])


# --------------------------------------------------------------------------- vectors


def pack(vec: list[float]) -> bytes:
    a = array("f", vec)
    norm = math.sqrt(sum(x * x for x in a)) or 1.0
    return array("f", (x / norm for x in a)).tobytes()  # stored unit-length


def unpack(blob: bytes) -> array[float]:
    a: array[float] = array("f")
    a.frombytes(blob)
    return a


def cosine_top(
    query: list[float], vectors: list[tuple[str, bytes]], k: int
) -> list[tuple[str, float]]:
    """Top-k by cosine similarity (vectors are stored normalised)."""
    q = unpack(pack(query))
    scored = []
    for key, blob in vectors:
        v = unpack(blob)
        if len(v) != len(q):
            continue  # a different embedding model; ignored until re-indexed
        scored.append((key, sum(a * b for a, b in zip(q, v, strict=True))))
    scored.sort(key=lambda kv: -kv[1])
    return scored[:k]


# --------------------------------------------------------------------------- answers

_CITE = re.compile(r"\[(\d{1,2})\]")


@dataclass(frozen=True)
class AnswerCheck:
    cited: list[int]  # valid source numbers used, in order of first use
    invalid: list[int]  # numbers that do not exist
    grounded: bool  # at least one valid citation and no invalid ones


def check_answer(text: str, n_sources: int) -> AnswerCheck:
    seen: list[int] = []
    bad: list[int] = []
    for m in _CITE.finditer(text):
        n = int(m.group(1))
        target = seen if 1 <= n <= n_sources else bad
        if n not in target:
            target.append(n)
    return AnswerCheck(seen, bad, bool(seen) and not bad)


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


@dataclass(frozen=True)
class DayPlan:
    top: list[str]  # task ids, most important first (max 3)
    reasons: dict[str, str]
    note: str


def parse_day_plan(text: str, allowed: set[str]) -> tuple[DayPlan, list[str]]:
    """Parse the model's plan; keep only task ids that were offered. Returns (plan, dropped ids)."""
    text = strip_think(text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    data: dict[str, object] = {}
    if m:
        try:
            loaded = json.loads(m.group(0))
            data = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            data = {}
    top: list[str] = []
    reasons: dict[str, str] = {}
    dropped: list[str] = []
    raw_top = data.get("top")
    for item in raw_top if isinstance(raw_top, list) else []:
        tid = str(item.get("id") if isinstance(item, dict) else item)
        if tid in allowed and tid not in top and len(top) < 3:
            top.append(tid)
            if isinstance(item, dict) and item.get("why"):
                reasons[tid] = " ".join(str(item["why"]).split())[:240]
        elif tid not in allowed:
            dropped.append(tid)
    note = " ".join(str(data.get("note", "")).split())[:400]
    return DayPlan(top, reasons, note), dropped
