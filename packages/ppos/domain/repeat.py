"""Repeating tasks: a small, well-defined subset of RFC 5545 RRULE.

Supported: FREQ=DAILY|WEEKLY|MONTHLY, INTERVAL=n (1–52), BYDAY=MO,TU,… (weekly only).
Completing a repeating task creates the next occurrence (see TaskService.move).
"""

from __future__ import annotations

from datetime import date, timedelta

from ppos.domain.meetings import Recurrence
from ppos.shared.errors import ValidationError

_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_FREQS = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}


def parse_rule(text: str | None) -> Recurrence | None:
    """'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH' -> Recurrence; None/'' -> None."""
    if not text or not text.strip():
        return None
    parts: dict[str, str] = {}
    for piece in text.strip().upper().removeprefix("RRULE:").split(";"):
        if not piece:
            continue
        key, sep, value = piece.partition("=")
        if not sep:
            raise ValidationError(f"invalid repeat rule part {piece!r}")
        parts[key] = value
    unknown = set(parts) - {"FREQ", "INTERVAL", "BYDAY"}
    if unknown:
        raise ValidationError(
            f"repeat rules support FREQ, INTERVAL and BYDAY only (not {sorted(unknown)[0]})"
        )
    freq = _FREQS.get(parts.get("FREQ", ""))
    if freq is None:
        raise ValidationError("repeat must be daily, weekly or monthly")
    try:
        interval = int(parts.get("INTERVAL", "1"))
    except ValueError as exc:
        raise ValidationError("repeat interval must be a number") from exc
    names = [d for d in (parts.get("BYDAY") or "").split(",") if d]
    if any(d not in _DAYS for d in names):
        raise ValidationError("weekdays are MO, TU, WE, TH, FR, SA, SU")
    days = tuple(_DAYS.index(d) for d in names)
    return Recurrence(freq, interval, days)


def to_rule(r: Recurrence) -> str:
    out = f"FREQ={r.freq.upper()}"
    if r.interval != 1:
        out += f";INTERVAL={r.interval}"
    if r.weekdays:
        out += ";BYDAY=" + ",".join(_DAYS[d] for d in r.weekdays)
    return out


def normalize_rule(text: str | None) -> str | None:
    """Validate and canonicalise a stored rule."""
    r = parse_rule(text)
    return to_rule(r) if r else None


def describe_rule(text: str | None) -> str:
    r = parse_rule(text)
    return r.describe() if r else ""


def next_after(text: str, anchor: date) -> date:
    """The first occurrence strictly after ``anchor`` (the date the last one was for)."""
    r = parse_rule(text)
    if r is None:
        raise ValidationError("not a repeating task")
    if r.freq == "monthly":
        # same day next month, clamped to the month's end (Jan 31 -> Feb 28), never skipped
        from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]

        result: date = anchor + relativedelta(months=r.interval)
        return result
    horizon = anchor + timedelta(days=400 * r.interval)
    for d in r.days(anchor, horizon):
        if d > anchor:
            return d
    raise ValidationError("this repeat rule has no next date")
