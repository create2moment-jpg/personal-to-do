"""Periodic reviews: periods, and the grounding rules for AI-drafted text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from ppos.domain.goals import period_bounds
from ppos.shared.errors import ValidationError

KINDS = ("month", "bimonth", "quarter", "year")
SECTIONS = ("highlights", "challenges", "learnings", "next_focus")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")  # fmt: skip
MAX_BULLETS = 6


def review_bounds(kind: str, period: str) -> tuple[date, date]:
    if kind == "bimonth":
        m = re.fullmatch(r"(\d{4})-B([1-6])", period)
        if not m:
            raise ValidationError("bi-monthly period must look like 2026-B6 (Nov–Dec)")
        year, n = int(m.group(1)), int(m.group(2))
        start = date(year, 2 * n - 1, 1)
        end = (date(year + 1, 1, 1) if n == 6 else date(year, 2 * n + 1, 1)) - timedelta(days=1)
        return start, end
    if kind not in KINDS:
        raise ValidationError(f"review kind must be one of {', '.join(KINDS)}")
    return period_bounds(kind, period)


def period_containing(kind: str, day: date) -> str:
    if kind == "month":
        return f"{day.year}-{day.month:02d}"
    if kind == "bimonth":
        return f"{day.year}-B{(day.month + 1) // 2}"
    if kind == "quarter":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    if kind == "year":
        return str(day.year)
    raise ValidationError(f"review kind must be one of {', '.join(KINDS)}")


def previous_period(kind: str, day: date) -> str:
    """The most recent period of this kind that has fully ended before ``day``."""
    start, _ = review_bounds(kind, period_containing(kind, day))
    return period_containing(kind, start - timedelta(days=1))


def period_label(kind: str, period: str) -> str:
    start, end = review_bounds(kind, period)
    if kind == "month":
        return f"{MONTHS[start.month - 1]} {start.year}"
    if kind == "bimonth":
        return f"{MONTHS[start.month - 1][:3]}–{MONTHS[end.month - 1][:3]} {start.year}"
    if kind == "quarter":
        return f"Q{(start.month - 1) // 3 + 1} {start.year}"
    return str(start.year)


@dataclass
class Review:
    id: str
    kind: str
    period: str
    created_at: datetime
    updated_at: datetime
    status: str = "draft"
    highlights: str = ""
    challenges: str = ""
    learnings: str = ""
    next_focus: str = ""
    snapshot: dict[str, Any] = field(default_factory=dict)
    ai_model: str | None = None
    ai_template: str | None = None
    finalized_at: datetime | None = None

    def __post_init__(self) -> None:
        review_bounds(self.kind, self.period)
        if self.status not in ("draft", "final"):
            raise ValidationError("status must be draft or final")

    @property
    def bounds(self) -> tuple[date, date]:
        return review_bounds(self.kind, self.period)


# --------------------------------------------------------------------------- AI grounding

_CITE = re.compile(r"\[([A-Z]\d{1,3})\]")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class DraftCheck:
    sections: dict[str, list[str]]
    dropped: list[tuple[str, str]]  # (bullet, reason)


def parse_draft(text: str) -> dict[str, list[str]]:
    """Tolerant JSON-object parse (strips <think> blocks and code fences)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key in SECTIONS:
        val = data.get(key)
        if isinstance(val, list):
            out[key] = [" ".join(str(b).split()) for b in val if str(b).strip()][:MAX_BULLETS]
    return out


def check_draft(raw: dict[str, list[str]], items: dict[str, str]) -> DraftCheck:
    """Keep only bullets that cite known items and whose numbers appear in what they cite."""
    kept: dict[str, list[str]] = {s: [] for s in SECTIONS}
    dropped: list[tuple[str, str]] = []
    for section, bullets in raw.items():
        for b in bullets:
            cites = _CITE.findall(b)
            if not cites:
                dropped.append((b, "cites nothing from your records"))
                continue
            unknown = [c for c in cites if c not in items]
            if unknown:
                dropped.append((b, f"cites unknown item {unknown[0]}"))
                continue
            sources = " ".join(items[c] for c in cites)
            src_numbers = {n.replace(",", ".") for n in _NUM.findall(sources)}
            numbers = {n.replace(",", ".") for n in _NUM.findall(_CITE.sub("", b))}
            if numbers - src_numbers:
                dropped.append(
                    (b, f"number {sorted(numbers - src_numbers)[0]} is not in the cited items")
                )
                continue
            kept[section].append(b)
    return DraftCheck(kept, dropped)
