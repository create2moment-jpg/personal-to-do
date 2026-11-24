"""Deterministic quick-capture parser.

Grammar (tokens may appear anywhere, order-independent):

    #tag            add a tag
    !1 .. !4        priority
    ~30m / ~2h      estimate (also ~1h30m)
    @today @tomorrow @mon..@sun @2026-12-01   schedule for a day
    due:2026-12-01  due date (also due:today / due:tomorrow / due:fri)
    +project-name   project hint (resolved by the application layer)
    idea: ...       prefix → goes to the Ideas inbox as a note
    note: ...       prefix → general note

The LLM-based capture (Phase 5) may *propose* richer structure, but this
parser is the deterministic baseline that always works offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from ppos.domain.tasks import Priority


class CaptureKind(str, Enum):
    TASK = "task"
    IDEA = "idea"
    NOTE = "note"


@dataclass
class ParsedCapture:
    kind: CaptureKind
    title: str
    tags: list[str] = field(default_factory=list)
    priority: Priority = Priority.P4
    estimate_minutes: int | None = None
    scheduled_date: date | None = None
    due_date: date | None = None
    project_hint: str | None = None


_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_EST_RE = re.compile(r"^~(?:(\d+)h)?(?:(\d+)m)?$")
_PREFIX_RE = re.compile(r"^\s*(idea|note|task)\s*:\s*", re.IGNORECASE)


def resolve_day(word: str, today: date) -> date | None:
    word = word.lower()
    if word == "today":
        return today
    if word in ("tomorrow", "tmr"):
        return today + timedelta(days=1)
    if word[:3] in _WEEKDAYS and len(word) <= 9:
        target = _WEEKDAYS.index(word[:3])
        delta = (target - today.weekday()) % 7 or 7  # always the *next* such day
        return today + timedelta(days=delta)
    try:
        return date.fromisoformat(word)
    except ValueError:
        return None


def parse_capture(text: str, today: date) -> ParsedCapture:
    kind = CaptureKind.TASK
    prefix = _PREFIX_RE.match(text)
    if prefix:
        kind = CaptureKind(prefix.group(1).lower())
        text = text[prefix.end() :]

    result = ParsedCapture(kind=kind, title="")
    words: list[str] = []
    for token in text.split():
        lower = token.lower()
        if kind != CaptureKind.TASK:
            # Notes/ideas keep their text verbatim except for tags.
            if token.startswith("#") and len(token) > 1:
                result.tags.append(token[1:])
            words.append(token)
            continue
        if token.startswith("#") and len(token) > 1:
            result.tags.append(token[1:])
        elif re.fullmatch(r"![1-4]", token):
            result.priority = Priority(int(token[1]))
        elif (m := _EST_RE.match(lower)) and (m.group(1) or m.group(2)):
            result.estimate_minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        elif lower.startswith("@") and (day := resolve_day(lower[1:], today)):
            result.scheduled_date = day
        elif lower.startswith("due:") and (day := resolve_day(lower[4:], today)):
            result.due_date = day
        elif token.startswith("+") and len(token) > 1:
            result.project_hint = token[1:].replace("-", " ").replace("_", " ")
        else:
            words.append(token)
    result.title = " ".join(words).strip()
    return result
