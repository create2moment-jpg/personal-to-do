"""Projects group tasks and notes; areas are free-text ongoing responsibilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ppos.shared.errors import ValidationError


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass
class Project:
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    description: str = ""
    area: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    color: str | None = None

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValidationError("project name must not be empty")
        if self.color is not None and not (len(self.color) == 7 and self.color.startswith("#")):
            raise ValidationError("color must be a #rrggbb hex string")
