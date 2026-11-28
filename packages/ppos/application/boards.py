"""Whiteboards: create from templates, load with live card data, save batched changes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.boards import MAX_ITEMS, TEMPLATES, Board, BoardItem
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

ITEM_FIELDS = (
    "kind",
    "x",
    "y",
    "w",
    "h",
    "z",
    "text",
    "color",
    "style",
    "ref_type",
    "ref_id",
    "from_id",
    "to_id",
)


@dataclass
class BoardView:
    board: Board
    items: list[BoardItem]
    refs: dict[str, dict[str, Any]]  # "task:<id>" -> live title/status, for cards


class BoardService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, tasks: TaskService) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks

    def all(self) -> list[tuple[Board, int]]:
        with self._uow() as uow:
            return uow.boards.all()

    def create(self, title: str = "", template: str = "blank", emoji: str | None = None) -> Board:
        if template not in TEMPLATES:
            raise ValidationError(f"template must be one of {', '.join(TEMPLATES)}")
        name, items = TEMPLATES[template]
        now = self._clock.now()
        board = Board(new_id(), title or name, now, now, emoji)
        with self._uow() as uow:
            uow.boards.add(board)
            for z, (kind, x, y, w, h, text, color, style) in enumerate(items):
                uow.boards.upsert_item(
                    BoardItem(
                        new_id(),
                        board.id,
                        kind,
                        now,
                        now,
                        x,
                        y,
                        w,
                        h,
                        float(z),
                        text,
                        color,
                        dict(style),
                    )
                )
            uow.audit.record("board", board.id, "create", details={"template": template})
            uow.commit()
        return board

    def get(self, board_id: str) -> BoardView:
        with self._uow() as uow:
            board = self._require(uow, board_id)
            items = uow.boards.items(board_id)
            refs: dict[str, dict[str, Any]] = {}
            for i in items:
                if i.kind != "card" or not i.ref_id:
                    continue
                key = f"{i.ref_type}:{i.ref_id}"
                if i.ref_type == "task":
                    t = uow.tasks.get(i.ref_id)
                    refs[key] = (
                        {
                            "title": t.title,
                            "status": t.status.value,
                            "due_date": t.due_date,
                            "missing": t.deleted_at is not None,
                        }
                        if t
                        else {"title": "Deleted task", "missing": True}
                    )
                else:
                    n = uow.notes.get(i.ref_id)
                    refs[key] = (
                        {"title": n.title, "kind": n.kind.value, "excerpt": n.body[:160]}
                        if n
                        else {"title": "Deleted note", "missing": True}
                    )
            return BoardView(board, items, refs)

    def update(self, board_id: str, changes: Mapping[str, Any]) -> Board:
        unknown = set(changes) - {"title", "emoji", "viewport"}
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            b = self._require(uow, board_id)
            for k, v in changes.items():
                setattr(b, k, v)
            b.updated_at = self._clock.now()
            Board.__post_init__(b)
            uow.boards.update(b)
            uow.commit()
            return b

    def delete(self, board_id: str) -> None:
        with self._uow() as uow:
            b = self._require(uow, board_id)
            uow.boards.delete(board_id)
            uow.audit.record("board", board_id, "delete", details={"title": b.title})
            uow.commit()

    def apply_changes(
        self, board_id: str, upserts: Sequence[Mapping[str, Any]], deletes: Sequence[str]
    ) -> int:
        """Save a batch of edits in one transaction; returns the new board version."""
        now = self._clock.now()
        with self._uow() as uow:
            board = self._require(uow, board_id)
            existing = {i.id: i for i in uow.boards.items(board_id)}
            if deletes:
                uow.boards.delete_items(board_id, list(deletes))
                for d in deletes:
                    existing.pop(d, None)
            new_items: list[BoardItem] = []
            for raw in upserts:
                item_id = str(raw.get("id") or "")
                prev = existing.get(item_id)
                values = {k: raw[k] for k in ITEM_FIELDS if k in raw}
                if prev is not None:
                    merged = {k: getattr(prev, k) for k in ITEM_FIELDS} | values
                    item = BoardItem(
                        item_id, board_id, created_at=prev.created_at, updated_at=now, **merged
                    )
                else:
                    if "kind" not in values:
                        raise ValidationError("a new item needs a kind")
                    item = BoardItem(item_id, board_id, created_at=now, updated_at=now, **values)
                existing[item.id] = item
                new_items.append(item)
            if len(existing) > MAX_ITEMS:
                raise ValidationError(f"a board holds at most {MAX_ITEMS} items")
            for item in new_items:
                if item.kind == "connector":
                    for end in (item.from_id, item.to_id):
                        if end not in existing:
                            raise ValidationError("an arrow must join items on this board")
                if item.kind == "card":
                    self._check_ref(uow, item)
                uow.boards.upsert_item(item)
            board.version += 1
            board.updated_at = now
            uow.boards.update(board)
            uow.commit()
            return board.version

    def to_task(self, board_id: str, item_id: str) -> BoardItem:
        """Turn a sticky (or text) into a task; the item becomes a live card in place."""
        with self._uow() as uow:
            self._require(uow, board_id)
            item = next((i for i in uow.boards.items(board_id) if i.id == item_id), None)
        if item is None:
            raise NotFoundError("board item", item_id)
        if item.kind not in ("sticky", "text"):
            raise ValidationError("only stickies and text become tasks")
        title = " ".join(item.text.split())[:200]
        if not title:
            raise ValidationError("write something on the sticky first")
        task = self._tasks.create(title, tags=["board"])
        now = self._clock.now()
        card = BoardItem(
            item.id,
            board_id,
            "card",
            item.created_at,
            now,
            item.x,
            item.y,
            max(item.w, 220.0),
            max(item.h, 90.0),
            item.z,
            "",
            item.color,
            {},
            "task",
            task.id,
        )
        with self._uow() as uow:
            uow.boards.upsert_item(card)
            b = self._require(uow, board_id)
            b.version += 1
            b.updated_at = now
            uow.boards.update(b)
            uow.audit.record("board", board_id, "sticky_to_task", details={"task_id": task.id})
            uow.commit()
        return card

    @staticmethod
    def _check_ref(uow: UnitOfWork, item: BoardItem) -> None:
        assert item.ref_id is not None
        found = (
            uow.tasks.get(item.ref_id) if item.ref_type == "task" else uow.notes.get(item.ref_id)
        )
        if found is None:
            raise NotFoundError(str(item.ref_type), item.ref_id)

    @staticmethod
    def _require(uow: UnitOfWork, board_id: str) -> Board:
        b = uow.boards.get(board_id)
        if b is None:
            raise NotFoundError("board", board_id)
        return b
