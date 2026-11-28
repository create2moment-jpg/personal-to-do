"""Whiteboards: an infinite canvas of stickies, text, shapes, frames, arrows and cards."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ppos.domain.book import clean_emoji
from ppos.shared.errors import ValidationError

ITEM_KINDS = ("sticky", "text", "shape", "frame", "connector", "card", "drawing", "image")
REF_TYPES = ("task", "note")
MAX_ITEMS = 5000
MAX_TEXT = 10_000
MAX_COORD = 1_000_000.0
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_POINTS = re.compile(r"^-?\d+(\.\d+)?,-?\d+(\.\d+)?( -?\d+(\.\d+)?,-?\d+(\.\d+)?)*$")
IMAGE_NAME = re.compile(r"^[0-9a-f]{64}\.(png|jpg|gif|webp)$")
IMAGE_TYPES = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
}
MAX_IMAGE = 10 * 1024 * 1024


def image_ext(data: bytes) -> str:
    """Image type from the content (magic bytes), never from a file name."""
    for magic, ext in IMAGE_TYPES.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise ValidationError("images must be PNG, JPEG, GIF or WebP")


_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$|^[a-z]{3,12}$")


@dataclass
class Board:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    emoji: str | None = None
    viewport: dict[str, float] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split())[:200] or "Untitled board"
        self.emoji = clean_emoji(self.emoji)
        vp = {k: float(v) for k, v in (self.viewport or {}).items() if k in ("x", "y", "zoom")}
        if any(not math.isfinite(v) or abs(v) > MAX_COORD for v in vp.values()):
            raise ValidationError("invalid viewport")
        self.viewport = vp


@dataclass
class BoardItem:
    id: str
    board_id: str
    kind: str
    created_at: datetime
    updated_at: datetime
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    z: float = 0.0
    text: str = ""
    color: str | None = None
    style: dict[str, Any] = field(default_factory=dict)
    ref_type: str | None = None
    ref_id: str | None = None
    from_id: str | None = None
    to_id: str | None = None

    def __post_init__(self) -> None:
        if not _ID.match(self.id):
            raise ValidationError("item ids are 1–64 letters, digits, - or _")
        if self.kind not in ITEM_KINDS:
            raise ValidationError(f"item kind must be one of {', '.join(ITEM_KINDS)}")
        for name in ("x", "y", "w", "h", "z"):
            v = float(getattr(self, name))
            if not math.isfinite(v) or abs(v) > MAX_COORD:
                raise ValidationError(f"{name} is out of range")
            setattr(self, name, v)
        if self.w < 0 or self.h < 0:
            raise ValidationError("width and height cannot be negative")
        if len(self.text) > MAX_TEXT:
            raise ValidationError("item text is too long")
        if self.color is not None and not _COLOR.match(self.color):
            raise ValidationError("color must be #rrggbb or a colour name")
        if len(str(self.style)) > 2000:
            raise ValidationError("item style is too large")
        if self.kind == "card":
            if self.ref_type not in REF_TYPES or not self.ref_id:
                raise ValidationError("a card refers to a task or a note")
        elif self.ref_type is not None or self.ref_id is not None:
            raise ValidationError("only cards refer to tasks or notes")
        if self.kind == "drawing" and not _POINTS.match(self.text):
            raise ValidationError("a drawing is a list of x,y points")
        if self.kind == "image" and not IMAGE_NAME.match(self.text):
            raise ValidationError("an image refers to an uploaded file")
        if self.kind == "connector":
            if not self.from_id or not self.to_id or self.from_id == self.to_id:
                raise ValidationError("an arrow joins two different items")
        elif self.from_id or self.to_id:
            raise ValidationError("only arrows join items")


# Templates: (kind, x, y, w, h, text, color, style)
_T = tuple[str, float, float, float, float, str, str | None, dict[str, Any]]
TEMPLATES: dict[str, tuple[str, list[_T]]] = {
    "blank": ("Blank board", []),
    "retro": (
        "Retrospective",
        [
            ("frame", 0, 0, 380, 520, "Went well", "green", {}),
            ("frame", 420, 0, 380, 520, "To improve", "orange", {}),
            ("frame", 840, 0, 380, 520, "Actions", "blue", {}),
            ("sticky", 30, 60, 160, 120, "Add a sticky (S) …", "yellow", {}),
        ],
    ),
    "swot": (
        "SWOT",
        [
            ("frame", 0, 0, 460, 360, "Strengths", "green", {}),
            ("frame", 500, 0, 460, 360, "Weaknesses", "red", {}),
            ("frame", 0, 400, 460, 360, "Opportunities", "blue", {}),
            ("frame", 500, 400, 460, 360, "Threats", "orange", {}),
        ],
    ),
    "week": (
        "Weekly planning",
        [
            ("frame", i * 300.0, 0, 280, 600, d, "gray", {})
            for i, d in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"))
        ],
    ),
    "mindmap": (
        "Mind map",
        [
            ("shape", 0, 0, 220, 90, "Central idea", "purple", {"shape": "ellipse"}),
        ],
    ),
}
