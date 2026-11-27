"""Periodic reviews built from your own records.

The numbers come from a deterministic snapshot; the text is yours. An optional
local-AI draft must cite snapshot items and may only use numbers that appear in
what it cites — everything else is dropped and reported.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from ppos.application.goals import GoalService
from ppos.application.meetings import MeetingService
from ppos.application.ports import TaskQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.career import EVIDENCE_KINDS
from ppos.domain.reviews import (
    KINDS,
    SECTIONS,
    Review,
    check_draft,
    parse_draft,
    period_containing,
    period_label,
    previous_period,
    review_bounds,
)
from ppos.domain.skills import LEVELS
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError

TemplateRunner = Callable[[str, dict[str, str]], tuple[str, str, str, int]]
DRAFT_TEMPLATE = "06_monthly/period_review/v1.md"
MAX_ITEMS = 120


@dataclass(frozen=True)
class DueReview:
    kind: str
    period: str
    label: str
    review_id: str | None
    status: str | None
    in_progress: bool  # the period has not ended yet


@dataclass(frozen=True)
class Draft:
    sections: dict[str, list[str]]
    dropped: list[tuple[str, str]]
    model: str
    template: str


_KIND_WORD = {"month": "monthly", "bimonth": "bi-monthly", "quarter": "quarterly", "year": "annual"}


def _fmt(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m}m")


class ReviewService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        meetings: MeetingService,
        goals: GoalService,
        run_template: TemplateRunner | None,
        enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._meetings = meetings
        self._goals = goals
        self._run = run_template
        self._enabled = enabled

    # -- listing --------------------------------------------------------------
    def due(self) -> list[DueReview]:
        """For each kind: the last finished period and the current one."""
        today = self._clock.today()
        with self._uow() as uow:
            existing = {(r.kind, r.period): r for r in uow.reviews.all()}
        out = []
        for kind in KINDS:
            for period, running in (
                (previous_period(kind, today), False),
                (period_containing(kind, today), True),
            ):
                r = existing.get((kind, period))
                out.append(
                    DueReview(
                        kind,
                        period,
                        period_label(kind, period),
                        r.id if r else None,
                        r.status if r else None,
                        running,
                    )
                )
        return out

    def all(self) -> list[Review]:
        with self._uow() as uow:
            return uow.reviews.all()

    def get(self, review_id: str) -> Review:
        with self._uow() as uow:
            return self._require(uow, review_id)

    # -- commands -------------------------------------------------------------
    def open(self, kind: str, period: str) -> Review:
        """The review for a period, created (with a fresh snapshot) on first open."""
        review_bounds(kind, period)
        with self._uow() as uow:
            existing = uow.reviews.by_period(kind, period)
        if existing:
            return existing
        snapshot = self.snapshot(kind, period)
        now = self._clock.now()
        r = Review(new_id(), kind, period, now, now, snapshot=snapshot)
        with self._uow() as uow:
            if uow.reviews.by_period(kind, period):  # created meanwhile
                raise ConflictError("this review already exists")
            uow.reviews.add(r)
            uow.audit.record("review", r.id, "create", details={"kind": kind, "period": period})
            uow.commit()
        return r

    def refresh(self, review_id: str) -> Review:
        r = self.get(review_id)
        if r.status == "final":
            raise ValidationError("a finalized review keeps its numbers — reopen it to refresh")
        r.snapshot = self.snapshot(r.kind, r.period)
        return self._save(r, "refresh")

    def update(self, review_id: str, changes: Mapping[str, Any]) -> Review:
        unknown = set(changes) - set(SECTIONS) - {"ai_model", "ai_template"}
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        r = self.get(review_id)
        if r.status == "final":
            raise ValidationError("reopen the review to edit it")
        for k, v in changes.items():
            setattr(r, k, str(v) if k in SECTIONS else v)
        return self._save(r, "update")

    def finalize(self, review_id: str, final: bool = True) -> Review:
        r = self.get(review_id)
        r.status = "final" if final else "draft"
        r.finalized_at = self._clock.now() if final else None
        return self._save(r, "finalize" if final else "reopen")

    def delete(self, review_id: str) -> None:
        with self._uow() as uow:
            self._require(uow, review_id)
            uow.reviews.delete(review_id)
            uow.audit.record("review", review_id, "delete")
            uow.commit()

    def draft_with_ai(self, review_id: str) -> Draft:
        if self._run is None or not self._enabled():
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError("Local AI is off — turn it on in Settings → Local AI.")
        r = self.get(review_id)
        return self._draft(
            r.snapshot, period_label(r.kind, r.period), _KIND_WORD[r.kind], ("review", r.id)
        )

    def draft_week(self, monday: date) -> Draft:
        """Grounded draft for the weekly review (Week → Review)."""
        if monday.weekday() != 0:
            raise ValidationError("a week starts on Monday")
        self._require_ai()
        end = monday + timedelta(days=6)
        label = f"the week of {monday.strftime('%d %b %Y').lstrip('0')}"
        return self._draft(
            self.snapshot_range(monday, end), label, "weekly", ("week", monday.isoformat())
        )

    def draft_sprint(self, sprint_id: str) -> Draft:
        """Grounded draft for a sprint review (summary and lessons)."""
        self._require_ai()
        with self._uow() as uow:
            sp = uow.sprints.get(sprint_id)
            if sp is None:
                raise NotFoundError("sprint", sprint_id)
        snap = self.snapshot_range(sp.start_date, sp.end_date)
        return self._draft(
            snap,
            f"{sp.name} ({sp.start_date.isoformat()} → {sp.end_date.isoformat()})",
            "sprint",
            ("sprint", sp.id),
        )

    def _require_ai(self) -> None:
        if self._run is None or not self._enabled():
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError("Local AI is off — turn it on in Settings → Local AI.")

    def _draft(
        self, snapshot: dict[str, Any], label: str, kind_word: str, subject: tuple[str, str]
    ) -> Draft:
        assert self._run is not None
        items = {i["id"]: i["text"] for i in snapshot.get("items", [])}
        if not items:
            raise ValidationError("nothing recorded in this period to draft from")
        text, model, template, _ = self._run(
            DRAFT_TEMPLATE,
            {
                "period_label": label,
                "kind": kind_word,
                "items": "\n".join(f"[{k}] {v}" for k, v in items.items()),
            },
        )
        checked = check_draft(parse_draft(text), items)
        with self._uow() as uow:
            uow.audit.record(
                subject[0],
                subject[1],
                "ai_draft",
                actor="ai",
                details={"model": model, "template": template, "dropped": len(checked.dropped)},
            )
            uow.commit()
        return Draft(checked.sections, checked.dropped, model, template)

    def markdown(self, review_id: str) -> str:
        r = self.get(review_id)
        s = r.snapshot
        t, tm = s.get("tasks", {}), s.get("time", {})
        lines = [
            f"# {period_label(r.kind, r.period)} — {_KIND_WORD[r.kind]} review",
            "",
        ]
        lines += [
            f"- Tasks completed: {t.get('completed', 0)}"
            f" ({_fmt(t.get('actual_minutes', 0))} logged)",
            f"- Meetings: {_fmt(tm.get('meeting_minutes', 0))}"
            f" of {_fmt(tm.get('work_minutes', 0))} working time",
            f"- Goals achieved: {sum(1 for g in s.get('goals', []) if g['status'] == 'achieved')}",
            f"- Evidence accepted: {len(s.get('evidence', []))}",
            "",
        ]
        for key, title in (
            ("highlights", "Highlights"),
            ("challenges", "Challenges"),
            ("learnings", "Learnings"),
            ("next_focus", "Next focus"),
        ):
            body = getattr(r, key).strip()
            if body:
                lines += [f"## {title}", "", body, ""]
        return "\n".join(lines).rstrip() + "\n"

    # -- the numbers ----------------------------------------------------------
    def snapshot(self, kind: str, period: str) -> dict[str, Any]:
        start, end = review_bounds(kind, period)
        return self.snapshot_range(start, end)

    def snapshot_range(self, start: date, end: date) -> dict[str, Any]:
        """The numbers and citeable items for any date range (inclusive)."""
        today = self._clock.today()
        upto = min(end, today)
        frm = datetime.combine(start, time.min, tzinfo=timezone.utc)
        to = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        items: list[dict[str, str]] = []
        counters: Counter[str] = Counter()

        def item(prefix: str, text: str) -> None:
            if len(items) < MAX_ITEMS:
                counters[prefix] += 1
                items.append({"id": f"{prefix}{counters[prefix]}", "text": text})

        with self._uow() as uow:
            done = uow.tasks.find(
                TaskQuery(
                    statuses=(TaskStatus.DONE,),
                    completed_from=frm,
                    completed_to=to,
                    top_level_only=True,
                    limit=5000,
                )
            )
            projects = {p.id: p.name for p in uow.projects.find()}
            sprints = [sp for sp in uow.sprints.find() if start <= sp.end_date <= end]
            sprint_rows = []
            for sp in sprints:
                tasks = uow.tasks.find(TaskQuery(sprint_id=sp.id, top_level_only=True, limit=1000))
                committed = [x for x in tasks if x.commitment != "stretch"]
                sprint_rows.append({
                    "name": sp.name, "goal": sp.goal, "committed": len(committed),
                    "done": sum(1 for x in committed if x.status == TaskStatus.DONE),
                    "status": sp.status.value,
                })  # fmt: skip
            notes = self._notes(uow, start, upto)
            ratings = uow.skills.ratings()
            skills = {s.id: s.name for s in uow.skills.all()}
            accepted = [
                f for k in EVIDENCE_KINDS for f in uow.facts.find(kind=k, status="accepted")
                if frm <= f.updated_at < to
            ]  # fmt: skip
            doc_titles = {d.id: d.title for d in uow.documents.find()}

        # tasks
        est = sum(x.estimate_minutes or 0 for x in done)
        actual = sum(x.actual_minutes for x in done)
        both = [x for x in done if x.estimate_minutes and x.actual_minutes]
        accuracy = (
            round(
                sum(x.actual_minutes for x in both) / sum(x.estimate_minutes or 0 for x in both), 2
            )
            if both
            else None
        )
        with_due = [x for x in done if x.due_date]
        on_time = sum(
            1
            for x in with_due
            if x.completed_at and x.completed_at.date() <= (x.due_date or date.max)
        )
        by_project: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for x in done:
            name = projects.get(x.project_id or "", "No project")
            by_project[name][0] += 1
            by_project[name][1] += x.actual_minutes or x.estimate_minutes or 0
        top_projects = sorted(by_project.items(), key=lambda kv: (-kv[1][0], kv[0]))[:6]
        item("S", f"{len(done)} tasks completed, {_fmt(est)} estimated, {_fmt(actual)} logged")
        if accuracy is not None:
            item(
                "S",
                f"Time logged was {round(accuracy * 100)}% of the estimate"
                f" on {len(both)} tasks with both",
            )
        if with_due:
            item("S", f"{on_time} of {len(with_due)} tasks with a due date were finished on time")
        for name, (n, mins) in top_projects:
            item("S", f"{name}: {n} tasks completed ({_fmt(mins)})")
        highlights = sorted(done, key=lambda x: (int(x.priority), -(x.estimate_minutes or 0)))[:12]
        for x in highlights:
            item(
                "T",
                f"Completed: {x.title}"
                + (f" ({projects[x.project_id]})" if x.project_id in projects else ""),
            )

        # time
        ins = self._meetings.insights(start, upto) if upto >= start else None
        time_block: dict[str, Any] = {}
        if ins is not None:
            share = round(ins.meeting_minutes / ins.work_minutes * 100) if ins.work_minutes else 0
            time_block = {
                "meeting_minutes": ins.meeting_minutes, "work_minutes": ins.work_minutes,
                "meeting_share": share, "meetings": ins.meetings_count, "calls": ins.calls_count,
                "by_person": [list(p) for p in ins.by_person[:5]],
                "by_topic": [list(t) for t in ins.by_topic[:5]],
                "avg_rating": ins.avg_rating,
            }  # fmt: skip
            item(
                "M",
                f"Meetings took {_fmt(ins.meeting_minutes)} of {_fmt(ins.work_minutes)}"
                f" working time ({share}%)",
            )
            item("M", f"{ins.meetings_count} meetings and {ins.calls_count} calls")
            for name, mins, n in ins.by_person[:3]:
                item("M", f"Time with {name}: {_fmt(mins)} over {n} meetings or calls")
            for name, mins, _n in ins.by_topic[:3]:
                item("M", f"Meeting time on {name}: {_fmt(mins)}")

        for row in sprint_rows:
            item(
                "P",
                f"{row['name']}: {row['done']} of {row['committed']} committed tasks done"
                + (f" — goal: {row['goal']}" if row["goal"] else ""),
            )

        # goals overlapping the period
        goal_rows = []
        for node in self._goals.all_nodes().values():
            g = node.goal
            gs, ge = g.bounds
            if ge < start or gs > end:
                continue
            pct = None if node.progress.value is None else round(node.progress.value * 100)
            achieved_here = g.achieved_at is not None and frm <= g.achieved_at < to
            goal_rows.append({
                "title": g.title, "horizon": g.horizon, "period": g.period,
                "status": g.status, "progress": pct, "pace": node.pace,
                "basis": node.progress.basis,
                "achieved_in_period": achieved_here,
            })  # fmt: skip
            if achieved_here:
                item("G", f"Goal achieved: {g.title}")
            elif g.status == "active":
                item(
                    "G",
                    f"Goal '{g.title}' at {'unmeasured' if pct is None else f'{pct}%'}"
                    f" ({node.progress.basis}; {node.pace})",
                )

        # skills: change of rating inside the period
        skill_rows = []
        by_skill: dict[str, list[Any]] = defaultdict(list)
        for rt in ratings:
            by_skill[rt.skill_id].append(rt)
        for sid, rs in by_skill.items():
            before = [x for x in rs if x.rated_at < frm]
            inside = [x for x in rs if frm <= x.rated_at < to]
            if not inside:
                continue
            old = before[-1].level if before else None
            new = inside[-1].level
            skill_rows.append({"name": skills.get(sid, "?"), "from": old, "to": new})
            if old != new:
                item(
                    "K",
                    f"{skills.get(sid, '?')}: rated {LEVELS[new][0]} ({new})"
                    + (
                        f", up from {LEVELS[old][0]} ({old})"
                        if old and new > old
                        else f", from {LEVELS[old][0]} ({old})"
                        if old
                        else ""
                    ),
                )

        evidence_rows = [
            {
                "kind": f.kind,
                "statement": f.statement,
                "document": doc_titles.get(f.document_id, "Document"),
            }
            for f in accepted
        ]
        for f in accepted[:10]:
            item(
                "E",
                f"Evidence ({f.kind}): {f.statement} — {doc_titles.get(f.document_id, 'Document')}",
            )
        for prefix, key in (("W", "wins"), ("L", "learnings"), ("B", "blockers")):
            for d, text in notes[key][:8]:
                item(prefix, f"{d}: {text}")

        return {
            "start": start.isoformat(), "end": end.isoformat(),
            "computed_at": self._clock.now().isoformat(),
            "complete": end < today,
            "tasks": {
                "completed": len(done), "estimated_minutes": est, "actual_minutes": actual,
                "accuracy": accuracy, "on_time": on_time, "with_due": len(with_due),
                "by_project": [[n, c, m] for n, (c, m) in top_projects],
                "top": [x.title for x in highlights],
            },
            "time": time_block, "sprints": sprint_rows, "goals": goal_rows, "skills": skill_rows,
            "evidence": evidence_rows,
            "notes": {k: [[d, t] for d, t in v] for k, v in notes.items()},
            "items": items,
        }  # fmt: skip

    def _notes(self, uow: UnitOfWork, start: date, end: date) -> dict[str, list[tuple[str, str]]]:
        out: dict[str, list[tuple[str, str]]] = {"wins": [], "learnings": [], "blockers": []}
        d = start
        while d <= end:
            p = uow.days.get(d)
            if p is not None:
                for key, text in (
                    ("wins", p.review.wins),
                    ("learnings", p.review.learning),
                    ("blockers", p.review.blockers),
                ):
                    if text.strip():
                        out[key].append((d.isoformat(), " ".join(text.split())[:300]))
            if d.weekday() == 0 and (w := uow.weeks.get(d)) is not None:
                for key, text in (
                    ("wins", w.review_wins),
                    ("learnings", w.review_lessons),
                    ("blockers", w.review_risks),
                ):
                    if text.strip():
                        out[key].append((f"week of {d.isoformat()}", " ".join(text.split())[:300]))
            d += timedelta(days=1)
        return out

    # -- helpers --------------------------------------------------------------
    def _save(self, r: Review, action: str) -> Review:
        r.updated_at = self._clock.now()
        with self._uow() as uow:
            uow.reviews.update(r)
            uow.audit.record("review", r.id, action)
            uow.commit()
        return r

    @staticmethod
    def _require(uow: UnitOfWork, review_id: str) -> Review:
        r = uow.reviews.get(review_id)
        if r is None:
            raise NotFoundError("review", review_id)
        return r
