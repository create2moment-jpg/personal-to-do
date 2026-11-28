"""Reusable checklists: a named list of task lines (quick-capture syntax)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ppos.shared.errors import ValidationError

MAX_LINES = 100


@dataclass
class Checklist:
    id: str
    name: str
    lines: list[str]
    uses: int
    created_at: datetime
    updated_at: datetime


def clean_lines(text: str) -> list[str]:
    """One item per line; list markers and empty checkboxes are dropped."""
    lines = [
        " ".join(ln.strip().lstrip("-*•").replace("[ ]", "").split()) for ln in text.splitlines()
    ]
    lines = [ln for ln in lines if ln]
    if len(lines) > MAX_LINES:
        raise ValidationError(f"a checklist holds at most {MAX_LINES} items")
    return lines
