"""Storage for workflow runs (proposals and what was applied)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from ppos.domain.workflows import Action, WorkflowRun


def _ts(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


class SqliteWorkflowRunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _from(r: sqlite3.Row) -> WorkflowRun:
        return WorkflowRun(
            id=r["id"],
            workflow=r["workflow"],
            created_at=datetime.fromisoformat(r["created_at"]),
            title=r["title"],
            summary=r["summary"],
            actions=[Action(**a) for a in json.loads(r["actions"])],
            notes=list(json.loads(r["notes"])),
            status=r["status"],
            applied_at=datetime.fromisoformat(r["applied_at"]) if r["applied_at"] else None,
        )

    def _values(self, run: WorkflowRun) -> tuple[object, ...]:
        return (
            run.workflow,
            _ts(run.created_at),
            run.title,
            run.summary,
            json.dumps([asdict(a) for a in run.actions], default=str),
            json.dumps(run.notes),
            run.status,
            _ts(run.applied_at),
            run.id,
        )

    def add(self, run: WorkflowRun) -> None:
        self._c.execute(
            "INSERT INTO workflow_runs (workflow, created_at, title, summary, actions, notes,"
            " status, applied_at, id) VALUES (?,?,?,?,?,?,?,?,?)",
            self._values(run),
        )

    def update(self, run: WorkflowRun) -> None:
        self._c.execute(
            "UPDATE workflow_runs SET workflow=?, created_at=?, title=?, summary=?, actions=?,"
            " notes=?, status=?, applied_at=? WHERE id=?",
            self._values(run),
        )

    def get(self, run_id: str) -> WorkflowRun | None:
        row = self._c.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        return self._from(row) if row else None

    def recent(self, limit: int = 20) -> list[WorkflowRun]:
        rows = self._c.execute(
            "SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [self._from(r) for r in rows]
