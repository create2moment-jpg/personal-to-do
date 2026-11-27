"""Skills matrix: self-assessed levels over time, targets, evidence-backed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ppos.shared.errors import ValidationError

LEVELS = {
    1: ("Aware", "Knows the basics and where to learn more"),
    2: ("Working", "Does routine work with some guidance"),
    3: ("Practitioner", "Works independently and reliably"),
    4: ("Advanced", "Handles hard cases; others ask for help"),
    5: ("Expert", "Sets direction and teaches across teams"),
}


def check_level(level: int | None, what: str = "level") -> None:
    if level is not None and level not in LEVELS:
        raise ValidationError(f"{what} must be 1–5")


@dataclass
class Skill:
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    category: str = "General"
    description: str = ""
    target_level: int | None = None
    position: float = 0.0

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        self.category = " ".join(self.category.split()) or "General"
        if not self.name:
            raise ValidationError("a skill needs a name")
        if len(self.name) > 120 or len(self.category) > 60:
            raise ValidationError("skill name ≤ 120 and category ≤ 60 characters")
        check_level(self.target_level, "target level")


@dataclass(frozen=True)
class Rating:
    id: str
    skill_id: str
    level: int
    rated_at: datetime
    note: str = ""

    def __post_init__(self) -> None:
        check_level(self.level)
