"""Career view: level expectations, user-confirmed evidence links, coverage per level.

Coverage is reported as a hypothesis about the evidence on file — never as a
promotion verdict. Only accepted facts count; nothing is linked automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ppos.application.meaning import MeaningMatcher
from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.career import (
    EVIDENCE_KINDS,
    EvidenceLink,
    Expectation,
    level_from_section,
    match_score,
    meaning_matches,
)
from ppos.domain.facts import Fact
from ppos.domain.tasks import Task
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError

UNLEVELLED = "Unlevelled"
MIN_SHARED_TERMS = 2
MAX_SUGGESTIONS = 5
DISCLAIMER = (
    "Coverage shows how much of each level's expectations has accepted evidence on file. "
    "It is a working hypothesis to guide what to collect next — not an assessment of "
    "readiness or a promotion verdict."
)


@dataclass(frozen=True)
class Evidence:
    fact: Fact
    document_title: str
    origin: str
    score: float | None
    note: str


@dataclass(frozen=True)
class Suggestion:
    fact: Fact
    document_title: str
    score: float
    shared: tuple[str, ...]
    similarity: float | None = None  # set when the match is by meaning


@dataclass
class ExpectationRow:
    expectation: Expectation
    evidence: list[Evidence] = field(default_factory=list)
    suggestion_count: int = 0


@dataclass
class LevelGroup:
    level: str
    rows: list[ExpectationRow]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def covered(self) -> int:
        return sum(1 for r in self.rows if r.evidence)


@dataclass
class CareerMatrix:
    levels: list[LevelGroup]
    evidence_pool: int  # accepted evidence facts available to link
    disclaimer: str = DISCLAIMER


def _level_key(level: str) -> tuple[int, str]:
    digits = "".join(ch for ch in level if ch.isdigit())
    return (0, f"{int(digits):04d}{level}") if digits else (1, level)


def _clean(text: str, what: str, limit: int) -> str:
    text = " ".join(text.split())
    if not text:
        raise ValidationError(f"{what} must not be empty")
    if len(text) > limit:
        raise ValidationError(f"{what} must be at most {limit} characters")
    return text


class CareerService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        tasks: TaskService,
        meaning: MeaningMatcher | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks
        self._meaning = meaning

    # -- framework ----------------------------------------------------------
    def sync(self) -> int:
        """Create expectations for accepted level-expectation facts (idempotent).

        Expectations whose source fact is no longer accepted are removed unless
        evidence has been linked to them (then they stay, owned by the user).
        """
        created = 0
        with self._uow() as uow:
            existing = {e.source_fact_id: e for e in uow.career.expectations() if e.source_fact_id}
            linked = {link.expectation_id for link in uow.career.links()}
            accepted = uow.facts.find(kind="level_expectation", status="accepted")
            accepted_ids = {f.id for f in accepted}
            now = self._clock.now()
            for f in accepted:
                if f.id in existing:
                    continue
                level = level_from_section(f.section) or UNLEVELLED
                uow.career.add_expectation(
                    Expectation(
                        id=new_id(),
                        level=level,
                        text=f.statement,
                        created_at=now,
                        updated_at=now,
                        source_fact_id=f.id,
                        position=uow.career.max_position(level) + 1,
                    )
                )
                created += 1
            for fid, e in existing.items():
                if fid not in accepted_ids and e.id not in linked:
                    uow.career.delete_expectation(e.id)
            if created:
                uow.audit.record("career", "framework", "sync", details={"created": created})
            uow.commit()
        return created

    def add_expectation(self, level: str, text: str, competency: str | None = None) -> Expectation:
        level = _clean(level, "level", 40)
        now = self._clock.now()
        with self._uow() as uow:
            e = Expectation(
                id=new_id(),
                level=level,
                text=_clean(text, "expectation", 400),
                created_at=now,
                updated_at=now,
                competency=_clean(competency, "competency", 80) if competency else None,
                position=uow.career.max_position(level) + 1,
            )
            uow.career.add_expectation(e)
            uow.audit.record("expectation", e.id, "create", details={"level": level})
            uow.commit()
            return e

    def update_expectation(
        self,
        expectation_id: str,
        level: str | None = None,
        text: str | None = None,
        competency: str | None = None,
    ) -> Expectation:
        with self._uow() as uow:
            e = self._require(uow, expectation_id)
            if level is not None:
                e.level = _clean(level, "level", 40)
            if text is not None:
                e.text = _clean(text, "expectation", 400)
            if competency is not None:
                e.competency = _clean(competency, "competency", 80) if competency.strip() else None
            e.updated_at = self._clock.now()
            uow.career.update_expectation(e)
            uow.audit.record("expectation", e.id, "update")
            uow.commit()
            return e

    def delete_expectation(self, expectation_id: str) -> None:
        with self._uow() as uow:
            e = self._require(uow, expectation_id)
            if e.source_fact_id:
                # Dismissing a framework row is done by rejecting its fact, so the
                # next sync does not bring it back.
                f = uow.facts.get(e.source_fact_id)
                if f is not None and f.status == "accepted":
                    f.status = "rejected"
                    f.updated_at = self._clock.now()
                    uow.facts.update(f)
            uow.career.delete_expectation(expectation_id)
            uow.audit.record("expectation", expectation_id, "delete")
            uow.commit()

    # -- evidence -----------------------------------------------------------
    def _evidence_facts(self, uow: UnitOfWork) -> list[Fact]:
        return [f for k in EVIDENCE_KINDS for f in uow.facts.find(kind=k, status="accepted")]

    def suggestions(self, expectation_id: str) -> list[Suggestion]:
        self._warm()
        with self._uow() as uow:
            e = self._require(uow, expectation_id)
            linked = {link.fact_id for link in uow.career.links() if link.expectation_id == e.id}
            titles = self._titles(uow)
            return self._suggest(e, self._evidence_facts(uow), linked, titles)

    def _by_meaning(self, query: str, pool: list[Fact]) -> dict[str, float]:
        if self._meaning is None:
            return {}
        sims = self._meaning.similarities(
            query, {f.id: f.statement for f in pool}, cached_only=True
        )
        return meaning_matches(sims)

    def _warm(self) -> None:
        """Embed expectations and evidence before a transaction opens (no model calls
        happen while the database is locked; a down server just means word matching)."""
        if self._meaning is None or not self._meaning.enabled:
            return
        with self._uow() as uow:
            queries = [f"{e.text} {e.competency or ''}".strip() for e in uow.career.expectations()]
            statements = [f.statement for f in self._evidence_facts(uow)]
        self._meaning.warm(queries + statements)

    def _suggest(
        self, e: Expectation, pool: list[Fact], linked: set[str], titles: dict[str, str]
    ) -> list[Suggestion]:
        query = f"{e.text} {e.competency or ''}".strip()
        candidates = [f for f in pool if f.id not in linked]
        meaning = self._by_meaning(query, candidates)
        out = []
        for f in candidates:
            m = match_score(query, f"{f.statement} {f.quote}")
            words = m if m and len(m.shared) >= MIN_SHARED_TERMS else None
            sim = meaning.get(f.id)
            if words is None and sim is None:
                continue
            out.append(
                Suggestion(
                    f,
                    titles.get(f.document_id, "Document"),
                    max(words.score if words else 0.0, sim or 0.0),
                    words.shared if words else (),
                    sim,
                )
            )
        out.sort(key=lambda s: (-s.score, -len(s.shared), s.fact.created_at))
        return out[:MAX_SUGGESTIONS]

    def link(self, expectation_id: str, fact_id: str, note: str = "") -> EvidenceLink:
        self._warm()
        with self._uow() as uow:
            e = self._require(uow, expectation_id)
            f = uow.facts.get(fact_id)
            if f is None:
                raise NotFoundError("fact", fact_id)
            if f.status != "accepted":
                raise ValidationError("only accepted facts can be used as evidence")
            if f.kind not in EVIDENCE_KINDS:
                raise ValidationError(f"a {f.kind.replace('_', ' ')} is not evidence")
            if uow.career.get_link(e.id, f.id):
                raise ConflictError("this fact is already linked to the expectation")
            linked = {x.fact_id for x in uow.career.links() if x.expectation_id == e.id}
            shown = self._suggest(e, self._evidence_facts(uow), linked, {})
            suggested = next((x for x in shown if x.fact.id == f.id), None)
            score = suggested.score if suggested else None
            link = EvidenceLink(
                id=new_id(),
                expectation_id=e.id,
                fact_id=f.id,
                origin="suggestion" if score is not None else "user",
                created_at=self._clock.now(),
                score=score,
                note=note.strip(),
            )
            uow.career.add_link(link)
            uow.audit.record("expectation", e.id, "link_evidence", details={"fact_id": f.id})
            uow.commit()
            return link

    def unlink(self, expectation_id: str, fact_id: str) -> None:
        with self._uow() as uow:
            if not uow.career.delete_link(expectation_id, fact_id):
                raise NotFoundError("evidence link", f"{expectation_id}/{fact_id}")
            uow.audit.record(
                "expectation", expectation_id, "unlink_evidence", details={"fact_id": fact_id}
            )
            uow.commit()

    # -- views --------------------------------------------------------------
    def matrix(self) -> CareerMatrix:
        self.sync()
        self._warm()
        with self._uow() as uow:
            titles = self._titles(uow)
            pool = self._evidence_facts(uow)
            by_id = {f.id: f for f in pool}
            links = uow.career.links()
            groups: dict[str, list[ExpectationRow]] = {}
            for e in uow.career.expectations():
                row = ExpectationRow(e)
                for link in links:
                    f = by_id.get(link.fact_id)
                    if link.expectation_id == e.id and f is not None:  # accepted evidence only
                        row.evidence.append(
                            Evidence(
                                f,
                                titles.get(f.document_id, "Document"),
                                link.origin,
                                link.score,
                                link.note,
                            )
                        )
                row.suggestion_count = len(
                    self._suggest(e, pool, {ev.fact.id for ev in row.evidence}, titles)
                )
                groups.setdefault(e.level, []).append(row)
            levels = [LevelGroup(lvl, groups[lvl]) for lvl in sorted(groups, key=_level_key)]
            return CareerMatrix(levels, len(pool))

    def gap_task(self, expectation_id: str) -> Task:
        with self._uow() as uow:
            e = self._require(uow, expectation_id)
        title = f"Build evidence ({e.level}): {e.text}"
        if len(title) > 200:
            title = title[:199].rstrip() + "…"
        return self._tasks.create(
            title,
            tags=["career", e.level.lower()],
            description=(
                f"Expectation at {e.level}: {e.text}\n\n"
                "Plan something concrete that would produce evidence for this, then record "
                "the outcome so it can be linked in the Career view."
            ),
        )

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _require(uow: UnitOfWork, expectation_id: str) -> Expectation:
        e = uow.career.get_expectation(expectation_id)
        if e is None:
            raise NotFoundError("expectation", expectation_id)
        return e

    @staticmethod
    def _titles(uow: UnitOfWork) -> dict[str, str]:
        return {d.id: d.title for d in uow.documents.find()}
