"""Agentic workflows (Phase 10): read your records, propose a checklist, apply what you keep.

Design (ADR-0004, "AI proposes, application decides"):
- A workflow only *reads* while proposing. Its output is a stored run with
  actions from a fixed allow-list (``ppos.domain.workflows.ACTION_KINDS``).
- Every action explains itself from your own records; nothing is invented.
  The local model is used only where a grounded helper already exists (the
  cited weekly-review draft) and the workflow works without it.
- Applying runs each kept action through the normal services, records its
  outcome on the run, and writes one audit entry for the approval.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from ppos.application.career import CareerService
from ppos.application.notes import NoteService
from ppos.application.planning import WeekService
from ppos.application.ports import TaskQuery, UnitOfWorkFactory
from ppos.application.reviews import ReviewService
from ppos.application.tasks import TaskService
from ppos.domain.goals import period_of
from ppos.domain.planning import monday_of
from ppos.domain.tasks import Task, TaskStatus
from ppos.domain.workflows import WORKFLOWS, Action, Candidate, WorkflowRun, fit_week
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, PposError, ValidationError

MAX_ACTIONS = 40
_DAY = "%a %d %b"


def _fmt_day(d: date) -> str:
    return d.strftime(_DAY).replace(" 0", " ")


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


class WorkflowService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        tasks: TaskService,
        weeks: WeekService,
        reviews: ReviewService,
        career: CareerService,
        notes: NoteService,
        default_task_minutes: Callable[[], int],
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks
        self._weeks = weeks
        self._reviews = reviews
        self._career = career
        self._notes = notes
        self._default_minutes = default_task_minutes

    # ------------------------------------------------------------------ runs
    def catalog(self) -> dict[str, str]:
        return dict(WORKFLOWS)

    def recent(self, limit: int = 20) -> list[WorkflowRun]:
        with self._uow() as uow:
            return uow.workflows.recent(limit)

    def get(self, run_id: str) -> WorkflowRun:
        with self._uow() as uow:
            run = uow.workflows.get(run_id)
        if run is None:
            raise NotFoundError("workflow run", run_id)
        return run

    def run(self, workflow: str, params: dict[str, Any] | None = None) -> WorkflowRun:
        params = params or {}
        builders = {
            "plan_week": self._plan_week,
            "week_review": self._week_review,
            "evidence_pack": self._evidence_pack,
        }
        if workflow not in builders:
            raise ValidationError(f"unknown workflow {workflow!r}")
        run = builders[workflow](params)
        run.actions = run.actions[:MAX_ACTIONS]
        with self._uow() as uow:
            uow.workflows.add(run)
            uow.audit.record(
                "workflow_run",
                run.id,
                "propose",
                actor="system",
                details={"workflow": workflow, "actions": len(run.actions)},
            )
            uow.commit()
        return run

    def dismiss(self, run_id: str) -> WorkflowRun:
        run = self._proposed(run_id)
        run.status = "dismissed"
        with self._uow() as uow:
            uow.workflows.update(run)
            uow.audit.record("workflow_run", run.id, "dismiss")
            uow.commit()
        return run

    def apply(self, run_id: str, action_ids: list[str]) -> WorkflowRun:
        """Apply the kept actions in order; each records its own outcome."""
        run = self._proposed(run_id)
        keep = set(action_ids)
        unknown = keep - {a.id for a in run.actions}
        if unknown:
            raise ValidationError(f"actions not in this run: {sorted(unknown)}")
        for a in run.actions:
            if a.id not in keep:
                a.outcome = "skipped"
                continue
            try:
                self._execute(a)
                a.outcome = "applied"
            except PposError as exc:
                a.outcome = f"failed: {exc}"[:300]
        run.status = "applied"
        run.applied_at = self._clock.now()
        with self._uow() as uow:
            uow.workflows.update(run)
            uow.audit.record(
                "workflow_run",
                run.id,
                "apply",
                details={
                    "workflow": run.workflow,
                    "applied": [a.id for a in run.actions if a.outcome == "applied"],
                    "failed": [a.id for a in run.actions if (a.outcome or "").startswith("failed")],
                },
            )
            uow.commit()
        return run

    def _proposed(self, run_id: str) -> WorkflowRun:
        run = self.get(run_id)
        if run.status != "proposed":
            raise ValidationError(f"this run was already {run.status}")
        return run

    def _new(self, workflow: str, title: str) -> WorkflowRun:
        return WorkflowRun(new_id(), workflow, self._clock.now(), title, "")

    # ------------------------------------------------------------ executors
    def _execute(self, a: Action) -> None:
        p = a.params
        if a.kind == "schedule_task":
            self._tasks.move(p["task_id"], scheduled_date=date.fromisoformat(p["day"]))
        elif a.kind == "set_objectives":
            self._weeks.update_plan(
                date.fromisoformat(p["week_start"]),
                {"objectives": [{"text": t} for t in p["objectives"]]},
            )
        elif a.kind == "set_week_review":
            week_start = date.fromisoformat(p["week_start"])
            plan = self._weeks.view(week_start).plan
            changes = {}
            for key, text in p["fields"].items():
                current = str(getattr(plan, key, "") or "").strip()
                changes[key] = f"{current}\n{text}".strip() if current else text  # never overwrite
            self._weeks.update_plan(week_start, changes)
        elif a.kind == "link_evidence":
            self._career.link(p["expectation_id"], p["fact_id"])
        elif a.kind == "gap_task":
            self._career.gap_task(p["expectation_id"])
        elif a.kind == "evidence_note":
            title, body = self._evidence_markdown(p["level"])
            self._notes.create(title=title, body=body)

    # ------------------------------------------------------- 1. plan my week
    def _plan_week(self, params: dict[str, Any]) -> WorkflowRun:
        anchor = date.fromisoformat(params["day"]) if params.get("day") else self._clock.today()
        week = self._weeks.view(anchor)
        monday, sunday = week.week_start, week.week_start + timedelta(days=6)
        today = self._clock.today()
        run = self._new("plan_week", f"Plan for the week of {_fmt_day(monday)}")
        free = {
            d.day: max(0, d.capacity_minutes - d.planned_minutes)
            for d in week.days
            if d.day >= today and d.time.work_minutes > 0
        }
        if not free:
            run.notes.append("No working days left in this week to plan.")

        default = self._default_minutes()
        open_statuses = (TaskStatus.PLANNED, TaskStatus.IN_PROGRESS)
        pool: dict[str, tuple[Task, str]] = {}
        for t in self._tasks.find(
            TaskQuery(statuses=open_statuses, scheduled_before=max(monday, today), limit=300)
        ):
            pool[t.id] = (
                t,
                f"overdue since {_fmt_day(t.scheduled_date)}" if t.scheduled_date else "",
            )
        for t in self._tasks.find(
            TaskQuery(statuses=(TaskStatus.BACKLOG,), unscheduled_only=True, limit=500)
        ):
            if t.due_date is not None and t.due_date <= sunday:
                pool.setdefault(t.id, (t, f"due {_fmt_day(t.due_date)}"))
        for t in week.sprint_backlog:
            if t.status != TaskStatus.DONE and t.scheduled_date is None:
                pool.setdefault(t.id, (t, "in the current sprint, not scheduled yet"))

        ordered = sorted(
            pool.values(),
            key=lambda tw: (
                tw[0].due_date or date.max,
                tw[0].status != TaskStatus.IN_PROGRESS,
                int(tw[0].priority),
                tw[0].position,
            ),
        )
        candidates = [
            Candidate(
                t.id,
                t.estimate_minutes or default,
                t.due_date if t.due_date and t.due_date >= min(free, default=today) else None,
            )
            for t, _ in ordered
        ]
        placed, unplaced = fit_week(candidates, free)
        by_id = {t.id: (t, why) for t, why in ordered}
        for task_id, day in placed:
            t, why = by_id[task_id]
            minutes = t.estimate_minutes or default
            run.actions.append(
                Action(
                    id=f"a{len(run.actions) + 1}",
                    kind="schedule_task",
                    label=f"Plan “{t.title}” on {_fmt_day(day)}",
                    params={"task_id": t.id, "day": day.isoformat()},
                    detail=f"{why} · {minutes} min · P{int(t.priority)}".lstrip(" ·"),
                )
            )
        if unplaced:
            names = ", ".join(f"“{by_id[i][0].title}”" for i in unplaced[:6])
            run.notes.append(
                f"Not enough free capacity this week for {len(unplaced)} task(s): {names}"
                + ("…" if len(unplaced) > 6 else "")
                + " — consider moving them to next week or dropping scope."
            )

        if not week.plan.objectives:
            objectives, source = self._goal_objectives(monday)
            if objectives:
                run.actions.append(
                    Action(
                        id=f"a{len(run.actions) + 1}",
                        kind="set_objectives",
                        label="Set this week's objectives: " + "; ".join(objectives),
                        params={"week_start": monday.isoformat(), "objectives": objectives},
                        detail=f"from your {source} goals",
                    )
                )
            else:
                run.notes.append(
                    "No weekly objectives set, and no active goals to suggest them from."
                )
        run.summary = (
            f"{len(placed)} task(s) fitted into this week's free capacity"
            + (f", {len(unplaced)} did not fit" if unplaced else "")
            + "."
        )
        return run

    def _goal_objectives(self, monday: date) -> tuple[list[str], str]:
        with self._uow() as uow:
            goals = [g for g in uow.goals.find(monday.year) if g.status == "active"]
        for horizon, label in (("month", "monthly"), ("quarter", "quarterly")):
            period = period_of(horizon, monday)
            picked = [g.title for g in goals if g.horizon == horizon and g.period == period]
            if picked:
                return picked[:3], label
        return [], ""

    # ------------------------------------------------ 2. weekly review prep
    def _week_review(self, params: dict[str, Any]) -> WorkflowRun:
        anchor = date.fromisoformat(params["day"]) if params.get("day") else self._clock.today()
        monday = monday_of(anchor)
        next_monday = monday + timedelta(days=7)
        review = self._weeks.review(anchor)
        plan = self._weeks.view(anchor).plan
        run = self._new("week_review", f"Weekly review for the week of {_fmt_day(monday)}")

        unfinished = [
            t
            for t in self._tasks.find(
                TaskQuery(scheduled_from=monday, scheduled_to=monday + timedelta(days=6), limit=500)
            )
            if t.status != TaskStatus.DONE
        ]
        for t in unfinished:
            run.actions.append(
                Action(
                    id=f"a{len(run.actions) + 1}",
                    kind="schedule_task",
                    label=f"Move “{t.title}” to {_fmt_day(next_monday)}",
                    params={"task_id": t.id, "day": next_monday.isoformat()},
                    detail=f"unfinished · was planned for {_fmt_day(t.scheduled_date)}"
                    if t.scheduled_date
                    else "unfinished",
                    selected=t.status != TaskStatus.BLOCKED,
                )
            )

        fields: dict[str, str] = {}
        if not plan.review_wins.strip() and review.done_titles:
            fields["review_wins"] = _bullets(review.done_titles[:8])
        model_note = ""
        try:
            draft = self._reviews.draft_week(monday)
            mapping = {
                "review_lessons": "learnings",
                "review_risks": "challenges",
                "review_next_focus": "next_focus",
            }
            for key, section in mapping.items():
                bullets = draft.sections.get(section) or []
                if bullets and not str(getattr(plan, key, "")).strip():
                    fields[key] = _bullets(bullets)
            model_note = (
                f" Lessons, risks and focus drafted by {draft.model}, each citing your records."
            )
            if draft.dropped:
                run.notes.append(
                    f"{len(draft.dropped)} drafted point(s) were dropped: not grounded."
                )
        except PposError as exc:
            run.notes.append(f"No AI draft ({exc}) — wins come from your finished tasks only.")
        if fields:
            run.actions.append(
                Action(
                    id=f"a{len(run.actions) + 1}",
                    kind="set_week_review",
                    label="Fill in the weekly review: "
                    + ", ".join(k.removeprefix("review_").replace("_", " ") for k in fields),
                    params={"week_start": monday.isoformat(), "fields": fields},
                    detail="added below anything you already wrote." + model_note,
                )
            )
        run.summary = (
            f"{review.done} done, {review.open} open this week; "
            f"{len(unfinished)} unfinished task(s) can move to next week."
        )
        return run

    # ------------------------------------------- 3. promotion evidence pack
    def _evidence_pack(self, params: dict[str, Any]) -> WorkflowRun:
        matrix = self._career.matrix()
        if not matrix.levels:
            raise ValidationError(
                "no level expectations yet — add your level framework in Knowledge or Career"
            )
        wanted = params.get("level")
        if wanted:
            group = next((g for g in matrix.levels if g.level == wanted), None)
            if group is None:
                raise NotFoundError("level", str(wanted))
        else:  # the first level that is not fully covered
            group = next((g for g in matrix.levels if g.covered < g.total), matrix.levels[-1])
        run = self._new("evidence_pack", f"Promotion evidence pack — {group.level}")
        for row in group.rows:
            if row.evidence:
                continue
            e = row.expectation
            suggestions = self._career.suggestions(e.id)
            if suggestions:
                s = suggestions[0]
                why = (
                    f"shares: {', '.join(s.shared)}"
                    if s.shared
                    else f"similar in meaning ({round((s.similarity or 0) * 100)}%)"
                )
                run.actions.append(
                    Action(
                        id=f"a{len(run.actions) + 1}",
                        kind="link_evidence",
                        label=f"Use “{s.fact.statement}” as evidence for “{e.text}”",
                        params={"expectation_id": e.id, "fact_id": s.fact.id},
                        detail=f"from {s.document_title} · {why}",
                    )
                )
            else:
                run.actions.append(
                    Action(
                        id=f"a{len(run.actions) + 1}",
                        kind="gap_task",
                        label=f"Create a task to build evidence for “{e.text}”",
                        params={"expectation_id": e.id},
                        detail="no accepted evidence matches it yet",
                    )
                )
        run.actions.append(
            Action(
                id=f"a{len(run.actions) + 1}",
                kind="evidence_note",
                label=f"Write the {group.level} evidence pack as a note",
                params={"level": group.level},
                detail="built after the links above, from accepted evidence only, with quotes",
            )
        )
        gaps = group.total - group.covered
        run.summary = (
            f"{group.level}: {group.covered} of {group.total} expectations have evidence; "
            f"{gaps} to cover."
        )
        run.notes.append(matrix.disclaimer)
        return run

    def _evidence_markdown(self, level: str) -> tuple[str, str]:
        matrix = self._career.matrix()
        group = next((g for g in matrix.levels if g.level == level), None)
        if group is None:
            raise NotFoundError("level", level)
        today = self._clock.today()
        lines = [
            f"Evidence on file for **{level}**, {today.isoformat()}: "
            f"{group.covered} of {group.total} expectations covered.",
            "",
            f"_{matrix.disclaimer}_",
            "",
        ]
        for row in group.rows:
            e = row.expectation
            lines.append(f"## {e.text}")
            if e.competency:
                lines.append(f"_Competency: {e.competency}_")
            if not row.evidence:
                lines.append("- *No evidence yet.*")
            for ev in row.evidence:
                lines.append(f"- {ev.fact.statement} — *{ev.document_title}*")
                if ev.fact.quote and ev.fact.quote != ev.fact.statement:
                    lines.append(f"  > {ev.fact.quote}")
            lines.append("")
        return f"Evidence pack — {level} ({today.isoformat()})", "\n".join(lines).strip() + "\n"
