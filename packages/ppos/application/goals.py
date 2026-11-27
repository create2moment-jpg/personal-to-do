"""Goals: create and organise year → quarter → month goals; compute progress and pace."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.goals import (
    Goal,
    Progress,
    check_parent,
    combine,
    own_progress,
    pace,
    period_of,
)
from ppos.domain.tasks import Task
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

EDITABLE = {
    "title", "description", "horizon", "period", "parent_id", "status", "progress_mode",
    "manual_progress", "metric_unit", "metric_start", "metric_target", "metric_current", "emoji",
    "position",
}  # fmt: skip


@dataclass
class GoalNode:
    goal: Goal
    progress: Progress
    pace: str
    expectation_ids: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    children: list[GoalNode] = field(default_factory=list)


@dataclass
class GoalTree:
    year: int
    roots: list[GoalNode]  # goals without a parent in this year (any horizon)


class GoalService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, tasks: TaskService) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks

    # -- commands -------------------------------------------------------------
    def create(self, title: str, horizon: str, period: str | None = None, **fields: Any) -> Goal:
        unknown = set(fields) - EDITABLE
        if unknown:
            raise ValidationError(f"unknown goal fields: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            g = Goal(
                id=new_id(),
                title=title,
                horizon=horizon,
                period=period or period_of(horizon, self._clock.today()),
                created_at=now,
                updated_at=now,
                **fields,
            )
            if g.parent_id:
                check_parent(g, self._require(uow, g.parent_id))
            g.position = uow.goals.max_position() + 1
            uow.goals.add(g)
            uow.audit.record("goal", g.id, "create", details={"title": g.title, "period": g.period})
            uow.commit()
            return g

    def update(self, goal_id: str, changes: Mapping[str, Any]) -> Goal:
        unknown = set(changes) - EDITABLE
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            g = self._require(uow, goal_id)
            for k, v in changes.items():
                setattr(g, k, v)
            if changes.get("status") == "achieved" and g.achieved_at is None:
                g.achieved_at = now
            elif "status" in changes and changes["status"] != "achieved":
                g.achieved_at = None
            g.updated_at = now
            Goal.__post_init__(g)
            if g.parent_id:
                if g.parent_id == g.id:
                    raise ValidationError("a goal cannot be its own parent")
                check_parent(g, self._require(uow, g.parent_id))
            for child in [x for x in uow.goals.find() if x.parent_id == g.id]:
                check_parent(child, g)  # keep existing sub-goals valid
            uow.goals.update(g)
            uow.audit.record(
                "goal", g.id, "update", details={k: str(v) for k, v in changes.items()}
            )
            uow.commit()
            return g

    def delete(self, goal_id: str) -> None:
        """Delete a goal; its sub-goals and tasks stay (they lose the link)."""
        with self._uow() as uow:
            self._require(uow, goal_id)
            uow.goals.delete(goal_id)
            uow.audit.record("goal", goal_id, "delete")
            uow.commit()

    def link(self, goal_id: str, kind: str, other_id: str, on: bool = True) -> None:
        table = {
            "expectation": "goal_expectations",
            "project": "goal_projects",
            "skill": "goal_skills",
        }.get(kind)
        if table is None:
            raise ValidationError("link kind must be expectation, project or skill")
        with self._uow() as uow:
            self._require(uow, goal_id)
            if on:
                exists: object = (
                    uow.career.get_expectation(other_id)
                    if kind == "expectation"
                    else uow.skills.get(other_id)
                    if kind == "skill"
                    else uow.projects.get(other_id)
                )
                if exists is None:
                    raise NotFoundError(kind, other_id)
                uow.goals.link(table, goal_id, other_id)
            elif not uow.goals.unlink(table, goal_id, other_id):
                raise NotFoundError(f"{kind} link", other_id)
            uow.audit.record("goal", goal_id, "link" if on else "unlink", details={kind: other_id})
            uow.commit()

    def add_task(self, goal_id: str, title: str, estimate_minutes: int | None = None) -> Task:
        with self._uow() as uow:
            self._require(uow, goal_id)
        return self._tasks.create(title, goal_id=goal_id, estimate_minutes=estimate_minutes)

    # -- queries --------------------------------------------------------------
    def tree(self, year: int | None = None) -> GoalTree:
        year = year or self._clock.today().year
        with self._uow() as uow:
            return GoalTree(year, self._build(uow, uow.goals.find(year)))

    def all_nodes(self) -> dict[str, GoalNode]:
        """Every goal with computed progress, by id (for other views, e.g. Career)."""
        with self._uow() as uow:
            roots = self._build(uow, uow.goals.find())
        out: dict[str, GoalNode] = {}
        stack = list(roots)
        while stack:
            n = stack.pop()
            out[n.goal.id] = n
            stack.extend(n.children)
        return out

    def tasks_of(self, goal_id: str) -> list[Task]:
        from ppos.application.ports import TaskQuery

        with self._uow() as uow:
            self._require(uow, goal_id)
            direct = uow.tasks.find(TaskQuery(goal_id=goal_id, top_level_only=True, limit=500))
            projects = [p for g, p in uow.goals.links("goal_projects") if g == goal_id]
            via = [
                t
                for p in projects
                for t in uow.tasks.find(TaskQuery(project_id=p, top_level_only=True, limit=500))
                if t.goal_id != goal_id
            ]
        return direct + via

    def _build(self, uow: UnitOfWork, goals: list[Goal]) -> list[GoalNode]:
        today = self._clock.today()
        exps: dict[str, list[str]] = defaultdict(list)
        for gid, e in uow.goals.links("goal_expectations"):
            exps[gid].append(e)
        projs: dict[str, list[str]] = defaultdict(list)
        project_goals: dict[str, list[str]] = defaultdict(list)
        for gid, p in uow.goals.links("goal_projects"):
            projs[gid].append(p)
            project_goals[p].append(gid)
        skills: dict[str, list[str]] = defaultdict(list)
        for gid, sid in uow.goals.links("goal_skills"):
            skills[gid].append(sid)
        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # done, total
        for goal_id, project_id, status in uow.goals.task_states():
            owners = set(project_goals.get(project_id or "", []))
            if goal_id:
                owners.add(goal_id)
            for o in owners:
                counts[o][1] += 1
                counts[o][0] += status == "done"
        ids = {g.id for g in goals}
        by_parent: dict[str | None, list[Goal]] = defaultdict(list)
        for g in goals:
            by_parent[g.parent_id if g.parent_id in ids else None].append(g)

        def node(g: Goal) -> GoalNode:
            children = [node(c) for c in by_parent.get(g.id, [])]
            done, total = counts[g.id]
            active_children = [c.progress for c in children if c.goal.status != "dropped"]
            prog = combine(g, own_progress(g, done, total), active_children)
            return GoalNode(
                g, prog, pace(g, prog, today), exps[g.id], projs[g.id], skills[g.id], children
            )

        order = {"year": 0, "quarter": 1, "month": 2}
        roots = sorted(by_parent[None], key=lambda g: (order[g.horizon], g.period, g.position))
        return [node(g) for g in roots]

    @staticmethod
    def _require(uow: UnitOfWork, goal_id: str) -> Goal:
        g = uow.goals.get(goal_id)
        if g is None:
            raise NotFoundError("goal", goal_id)
        return g
