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
    call: ...       prefix → log a call: ``call: Priya, Marcus / ADR review ~30m #topic @14:00``
                    (people before "/", purpose after; without "/" the first word is the person;
                    ~duration, #topic, @HH:MM start — default: just ended)
    meeting: ...    prefix (also ``mtg:``) → add a meeting, once or recurring:
                    ``meeting: Planning @mon @10:00 ~1h30 every 2 weeks with Ana, Ben #team``
                    repeats: daily · weekdays · weekly · monthly · every 2 weeks ·
                    every mon,thu · until 2027-03-01 · 10 times; people: ``with A, B``
                    or ``A, B / title``; ``on fri`` without a repeat means next Friday

The LLM-based capture (Phase 5) may *propose* richer structure, but this
parser is the deterministic baseline that always works offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from ppos.domain.meetings import Recurrence
from ppos.domain.tasks import Priority
from ppos.shared.errors import ValidationError


class CaptureKind(str, Enum):
    TASK = "task"
    IDEA = "idea"
    NOTE = "note"
    CALL = "call"
    MEETING = "meeting"


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
    people: list[str] = field(default_factory=list)
    start_time: str | None = None  # HH:MM for calls and meetings
    recurrence: Recurrence | None = None  # meetings only


_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_EST_RE = re.compile(r"^~(?:(\d+)h)?(?:(\d+)m)?$")
_PREFIX_RE = re.compile(r"^\s*(idea|note|task|call|meeting|mtg)\s*:\s*", re.IGNORECASE)
_HHMM_RE = re.compile(r"^@([01]?\d|2[0-3]):([0-5]\d)$")


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
        word = prefix.group(1).lower()
        kind = CaptureKind("meeting" if word == "mtg" else word)
        text = text[prefix.end() :]

    if kind == CaptureKind.CALL:
        return _parse_call(text)
    if kind == CaptureKind.MEETING:
        return _parse_meeting(text, today)

    repeat: Recurrence | None = None
    if kind == CaptureKind.TASK:
        text, repeat = _task_repeat(text)

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
    result.recurrence = repeat
    return result


def _task_repeat(text: str) -> tuple[str, Recurrence | None]:
    """Explicit 'every …' phrases only, so a title like 'Write daily report' stays intact."""
    patterns: list[tuple[str, object]] = [
        (r"\bevery\s+(\d{1,2})\s+(day|week|month)s?\b", "n"),
        (r"\bevery\s+weekday\b", Recurrence("weekly", 1, (0, 1, 2, 3, 4))),
        (rf"\bevery\s+({_DAYS})\b", "days"),
        (r"\bevery\s+day\b", Recurrence("daily")),
        (r"\bevery\s+week\b", Recurrence("weekly")),
        (r"\bevery\s+month\b", Recurrence("monthly")),
    ]
    for pattern, what in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        rest = (text[: m.start()] + " " + text[m.end() :]).strip()
        if what == "n":
            freq = {"day": "daily", "week": "weekly", "month": "monthly"}[m.group(2).lower()]
            return rest, Recurrence(freq, int(m.group(1)))
        if what == "days":
            return rest, Recurrence("weekly", 1, _weekdays(m.group(1)))
        assert isinstance(what, Recurrence)
        return rest, what
    return text, None


def _parse_call(text: str) -> ParsedCapture:
    result = ParsedCapture(kind=CaptureKind.CALL, title="")
    words: list[str] = []
    for token in text.split():
        if token.startswith("#") and len(token) > 1:
            result.tags.append(token[1:])
        elif (m := _EST_RE.match(token.lower())) and (m.group(1) or m.group(2)):
            result.estimate_minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        elif m2 := _HHMM_RE.match(token):
            result.start_time = f"{int(m2.group(1)):02d}:{m2.group(2)}"
        else:
            words.append(token)
    rest = " ".join(words)
    if "/" in rest:
        who, _, purpose = rest.partition("/")
        result.people = [p.strip() for p in who.split(",") if p.strip()]
        result.title = purpose.strip()
    elif words:
        result.people = [words[0].strip(",")]
        result.title = " ".join(words[1:])
    return result


_DAY = (  # real weekday names only ("month" is not "mon")
    r"(?:mon(?:day)?|tues?(?:day)?|wed(?:nesday)?|thu(?:rs?(?:day)?)?"
    r"|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b"
)
_DAYS = rf"{_DAY}(?:\s*(?:,|\band\b|&)\s*{_DAY})*"


def _weekdays(spec: str) -> tuple[int, ...]:
    return tuple(_WEEKDAYS.index(d[:3]) for d in re.findall(_DAY, spec.lower()))


def _parse_meeting(text: str, today: date) -> ParsedCapture:
    """``meeting:`` capture — phrases first (repeat, end, people), then tokens."""
    result = ParsedCapture(kind=CaptureKind.MEETING, title="")

    def take(pattern: str) -> re.Match[str] | None:
        nonlocal text
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            text = (text[: m.start()] + " " + text[m.end() :]).strip()
        return m

    freq: str | None = None
    interval = 1
    days: tuple[int, ...] = ()
    if m := take(r"\bevery\s+(\d{1,2})\s+(day|week|month)s?\b"):
        interval, freq = (
            int(m.group(1)),
            {"day": "daily", "week": "weekly", "month": "monthly"}[m.group(2).lower()],
        )
    if take(r"\b(?:every\s+)?weekdays?\b|\bevery\s+weekday\b"):
        freq, days = "weekly", (0, 1, 2, 3, 4)
    elif m := take(rf"\bevery\s+({_DAYS})\b"):
        freq, days = "weekly", _weekdays(m.group(1))
    if freq is None:
        for pattern, f in (
            (r"\bdaily\b|\bevery\s+day\b", "daily"),
            (r"\bweekly\b|\bevery\s+week\b", "weekly"),
            (r"\bmonthly\b|\bevery\s+month\b", "monthly"),
        ):
            if take(pattern):
                freq = f
                break
    on = take(rf"\bon\s+({_DAYS})\b")
    if on and freq == "weekly" and not days:
        days = _weekdays(on.group(1))
    elif on and freq is None:
        result.scheduled_date = resolve_day(on.group(1).split(",")[0].strip(), today)
    until = None
    if (m := take(r"\buntil\s+(\S+)")) and freq:
        until = resolve_day(m.group(1), today)
    count = None
    if (m := take(r"\b(\d{1,4})\s*(?:times|x)\b")) and freq:
        count = int(m.group(1))
    if m := take(r"\bwith\s+(.+?)(?=\s+[#@~]|$)"):
        result.people = [p.strip() for p in re.split(r",|\band\b|&", m.group(1)) if p.strip()]
    if freq:
        try:
            result.recurrence = Recurrence(freq, interval, days, until=until, count=count)
        except ValidationError:  # e.g. both "until" and "N times": keep the repeat, drop the end
            result.recurrence = Recurrence(freq, interval, days)

    words: list[str] = []
    for token in text.split():
        lower = token.lower()
        if token.startswith("#") and len(token) > 1:
            result.tags.append(token[1:])
        elif (m := _EST_RE.match(lower)) and (m.group(1) or m.group(2)):
            result.estimate_minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        elif m2 := re.fullmatch(r"~(\d+)h(\d{1,2})", lower):  # ~1h30
            result.estimate_minutes = int(m2.group(1)) * 60 + int(m2.group(2))
        elif m3 := _HHMM_RE.match(token):
            result.start_time = f"{int(m3.group(1)):02d}:{m3.group(2)}"
        elif lower.startswith("@") and (day := resolve_day(lower[1:], today)):
            result.scheduled_date = day
        else:
            words.append(token)
    rest = " ".join(words)
    if "/" in rest and not result.people:
        who, _, rest = rest.partition("/")
        result.people = [p.strip() for p in who.split(",") if p.strip()]
    result.title = rest.strip()
    return result
