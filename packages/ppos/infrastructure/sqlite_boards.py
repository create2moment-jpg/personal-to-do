"""Storage for whiteboards and their items."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ppos.domain.boards import Board, BoardItem

_ITEM_COLS = (
    "id, board_id, kind, x, y, w, h, z, text, color, style, ref_type, ref_id, from_id, to_id,"
    " created_at, updated_at"
)


class SqliteBoardRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _board(r: sqlite3.Row) -> Board:
        return Board(
            id=r["id"],
            title=r["title"],
            emoji=r["emoji"],
            viewport=json.loads(r["viewport"] or "{}"),
            version=r["version"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )

    @staticmethod
    def _item(r: sqlite3.Row) -> BoardItem:
        return BoardItem(
            id=r["id"],
            board_id=r["board_id"],
            kind=r["kind"],
            x=r["x"],
            y=r["y"],
            w=r["w"],
            h=r["h"],
            z=r["z"],
            text=r["text"],
            color=r["color"],
            style=json.loads(r["style"] or "{}"),
            ref_type=r["ref_type"],
            ref_id=r["ref_id"],
            from_id=r["from_id"],
            to_id=r["to_id"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )

    def add(self, b: Board) -> None:
        self._c.execute(
            "INSERT INTO boards (id, title, emoji, viewport, version, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (b.id, b.title, b.emoji, json.dumps(b.viewport), b.version,
             b.created_at.isoformat(), b.updated_at.isoformat()),
        )  # fmt: skip

    def update(self, b: Board) -> None:
        self._c.execute(
            "UPDATE boards SET title=?, emoji=?, viewport=?, version=?, updated_at=? WHERE id=?",
            (b.title, b.emoji, json.dumps(b.viewport), b.version, b.updated_at.isoformat(), b.id),
        )

    def get(self, board_id: str) -> Board | None:
        r = self._c.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
        return self._board(r) if r else None

    def all(self) -> list[tuple[Board, int]]:
        rows = self._c.execute(
            "SELECT b.*, (SELECT count(*) FROM board_items i WHERE i.board_id = b.id) AS n"
            " FROM boards b ORDER BY b.updated_at DESC"
        )
        return [(self._board(r), int(r["n"])) for r in rows]

    def delete(self, board_id: str) -> None:
        self._c.execute("DELETE FROM boards WHERE id = ?", (board_id,))

    def items(self, board_id: str) -> list[BoardItem]:
        rows = self._c.execute(
            f"SELECT {_ITEM_COLS} FROM board_items WHERE board_id = ? ORDER BY z, created_at",
            (board_id,),
        )
        return [self._item(r) for r in rows]

    def item_ids(self, board_id: str) -> set[str]:
        rows = self._c.execute("SELECT id FROM board_items WHERE board_id = ?", (board_id,))
        return {r[0] for r in rows}

    def upsert_item(self, i: BoardItem) -> None:
        self._c.execute(
            f"INSERT INTO board_items ({_ITEM_COLS}) VALUES ({','.join('?' * 17)})"
            " ON CONFLICT (board_id, id) DO UPDATE SET kind=excluded.kind, x=excluded.x,"
            " y=excluded.y, w=excluded.w, h=excluded.h, z=excluded.z, text=excluded.text,"
            " color=excluded.color, style=excluded.style, ref_type=excluded.ref_type,"
            " ref_id=excluded.ref_id, from_id=excluded.from_id, to_id=excluded.to_id,"
            " updated_at=excluded.updated_at",
            (i.id, i.board_id, i.kind, i.x, i.y, i.w, i.h, i.z, i.text, i.color,
             json.dumps(i.style), i.ref_type, i.ref_id, i.from_id, i.to_id,
             i.created_at.isoformat(), i.updated_at.isoformat()),
        )  # fmt: skip

    def delete_items(self, board_id: str, ids: list[str]) -> None:
        self._c.executemany(
            "DELETE FROM board_items WHERE board_id = ? AND id = ?", [(board_id, i) for i in ids]
        )
        # arrows attached to removed items go with them
        self._c.executemany(
            "DELETE FROM board_items WHERE board_id = ? AND kind = 'connector'"
            " AND (from_id = ? OR to_id = ?)",
            [(board_id, i, i) for i in ids],
        )
