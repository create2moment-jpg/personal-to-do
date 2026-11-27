"""Skills matrix: self-ratings with history, targets, evidence and growth goals.

Ratings are the user's own assessment; evidence links are made or confirmed by
the user and use accepted facts only. Nothing here is an external judgement.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from ppos.application.goals import GoalService
from ppos.application.meaning import MeaningMatcher
from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.domain.career import EVIDENCE_KINDS, match_score, meaning_matches
from ppos.domain.facts import Fact
from ppos.domain.goals import Goal, period_of
from ppos.domain.skills import LEVELS, Rating, Skill, check_level
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError

MIN_SHARED = 1  # skill names are short: one shared meaningful word is a useful hint
TREND_DAYS = 90


@dataclass(frozen=True)
class SkillEvidence:
    fact: Fact
    document_title: str
    origin: str


@dataclass(frozen=True)
class EvidenceHint:
    fact: Fact
    document_title: str
    score: float
    shared: tuple[str, ...]
    similarity: float | None = None  # set when the match is by meaning


@dataclass
class SkillRow:
    skill: Skill
    level: int | None  # latest self-rating
    previous: int | None  # rating ~90 days ago (for the trend)
    rated_at: str | None
    history: list[Rating] = field(default_factory=list)
    evidence: list[SkillEvidence] = field(default_factory=list)
    suggestion_count: int = 0
    goal_ids: list[str] = field(default_factory=list)

    @property
    def gap(self) -> int | None:
        if self.skill.target_level is None:
            return None
        return max(self.skill.target_level - (self.level or 0), 0)


@dataclass
class SkillMatrix:
    categories: list[tuple[str, list[SkillRow]]]
    levels: dict[int, tuple[str, str]]
    candidates: list[Fact]  # accepted competencies not yet tied to a skill


class SkillService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        goals: GoalService,
        meaning: MeaningMatcher | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._goals = goals
        self._meaning = meaning

    @staticmethod
    def _query(s: Skill) -> str:
        return f"{s.name} {s.description}".strip()

    def _warm(self) -> None:
        """Embed skills and evidence before a transaction opens (see CareerService)."""
        if self._meaning is None or not self._meaning.enabled:
            return
        with self._uow() as uow:
            texts = [self._query(s) for s in uow.skills.all()]
            texts += [f.statement for f in self._pool(uow)]
        self._meaning.warm(texts)

    # -- skills -----------------------------------------------------------------
    def create(
        self,
        name: str,
        category: str = "General",
        description: str = "",
        target_level: int | None = None,
        level: int | None = None,
        from_fact_id: str | None = None,
    ) -> Skill:
        now = self._clock.now()
        with self._uow() as uow:
            if uow.skills.by_name(name.strip()):
                raise ConflictError(f"you already track a skill called {name.strip()!r}")
            s = Skill(new_id(), name, now, now, category, description, target_level)
            s.position = uow.skills.max_position() + 1
            uow.skills.add(s)
            if level is not None:
                uow.skills.add_rating(Rating(new_id(), s.id, level, now, "first rating"))
            if from_fact_id:
                self._link(uow, s.id, from_fact_id, "user")
            uow.audit.record("skill", s.id, "create", details={"name": s.name})
            uow.commit()
            return s

    def update(self, skill_id: str, changes: Mapping[str, Any]) -> Skill:
        allowed = {"name", "category", "description", "target_level", "position"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            s = self._require(uow, skill_id)
            other = uow.skills.by_name(str(changes["name"]).strip()) if "name" in changes else None
            if other is not None and other.id != s.id:
                raise ConflictError("another skill already has that name")
            for k, v in changes.items():
                setattr(s, k, v)
            s.updated_at = self._clock.now()
            Skill.__post_init__(s)
            uow.skills.update(s)
            uow.audit.record("skill", s.id, "update")
            uow.commit()
            return s

    def delete(self, skill_id: str) -> None:
        with self._uow() as uow:
            self._require(uow, skill_id)
            uow.skills.delete(skill_id)
            uow.audit.record("skill", skill_id, "delete")
            uow.commit()

    def rate(self, skill_id: str, level: int, note: str = "") -> Rating:
        """Record a self-assessment; earlier ratings stay as history."""
        check_level(level)
        with self._uow() as uow:
            self._require(uow, skill_id)
            r = Rating(new_id(), skill_id, level, self._clock.now(), note.strip())
            uow.skills.add_rating(r)
            uow.audit.record("skill", skill_id, "rate", details={"level": level})
            uow.commit()
            return r

    # -- evidence ---------------------------------------------------------------
    def suggestions(self, skill_id: str) -> list[EvidenceHint]:
        self._warm()
        with self._uow() as uow:
            s = self._require(uow, skill_id)
            linked = {f for sid, f, _ in uow.skills.evidence() if sid == skill_id}
            return self._hints(s, self._pool(uow), linked, self._titles(uow))

    def link(self, skill_id: str, fact_id: str) -> str:
        self._warm()
        with self._uow() as uow:
            s = self._require(uow, skill_id)
            f = uow.facts.get(fact_id)
            if f is None:
                raise NotFoundError("fact", fact_id)
            linked = {x for sid, x, _ in uow.skills.evidence() if sid == skill_id}
            shown = self._hints(s, self._pool(uow), linked, {})
            origin = "suggestion" if any(h.fact.id == f.id for h in shown) else "user"
            self._link(uow, skill_id, fact_id, origin)
            uow.audit.record("skill", skill_id, "link_evidence", details={"fact_id": fact_id})
            uow.commit()
            return origin

    def unlink(self, skill_id: str, fact_id: str) -> None:
        with self._uow() as uow:
            if not uow.skills.unlink_evidence(skill_id, fact_id):
                raise NotFoundError("evidence link", f"{skill_id}/{fact_id}")
            uow.audit.record("skill", skill_id, "unlink_evidence", details={"fact_id": fact_id})
            uow.commit()

    def _link(self, uow: UnitOfWork, skill_id: str, fact_id: str, origin: str) -> None:
        f = uow.facts.get(fact_id)
        if f is None:
            raise NotFoundError("fact", fact_id)
        if f.status != "accepted" or f.kind not in EVIDENCE_KINDS:
            raise ValidationError(
                "only accepted achievements, responsibilities, competencies or strengths"
                " count as evidence"
            )
        if not uow.skills.link_evidence(skill_id, fact_id, origin, self._clock.now()):
            raise ConflictError("this fact is already linked to the skill")

    # -- growth -----------------------------------------------------------------
    def growth_goal(self, skill_id: str) -> Goal:
        """Turn a gap into a quarter goal for the current quarter, linked to the skill."""
        with self._uow() as uow:
            s = self._require(uow, skill_id)
            current = self._latest(uow).get(skill_id)
        lvl = current.level if current else None
        target = s.target_level or min((lvl or 0) + 1, 5)
        start = f"{LEVELS[lvl][0]} ({lvl})" if lvl else "unrated"
        goal = self._goals.create(
            f"Grow {s.name}: {start} → {LEVELS[target][0]} ({target})",
            "quarter",
            period_of("quarter", self._clock.today()),
            description=f"Target: {LEVELS[target][1].lower()}.",
            emoji="🌱",
        )
        self._goals.link(goal.id, "skill", s.id)
        return goal

    # -- view -------------------------------------------------------------------
    def matrix(self) -> SkillMatrix:
        self._warm()
        with self._uow() as uow:
            skills = uow.skills.all()
            ratings: dict[str, list[Rating]] = defaultdict(list)
            for r in uow.skills.ratings():
                ratings[r.skill_id].append(r)
            pool = self._pool(uow)
            by_id = {f.id: f for f in pool}
            titles = self._titles(uow)
            links = uow.skills.evidence()
            goal_links = uow.goals.links("goal_skills")
        cutoff = self._clock.now() - timedelta(days=TREND_DAYS)
        rows: dict[str, list[SkillRow]] = defaultdict(list)
        tied: set[str] = set()
        for s in skills:
            hist = ratings.get(s.id, [])
            before = [r for r in hist if r.rated_at <= cutoff]
            prev = before[-1].level if before else (hist[0].level if len(hist) > 1 else None)
            row = SkillRow(
                s,
                hist[-1].level if hist else None,
                prev,
                hist[-1].rated_at.isoformat() if hist else None,
                list(reversed(hist[-12:])),
            )
            for sid, fid, origin in links:
                if sid == s.id and fid in by_id:  # accepted evidence only
                    f = by_id[fid]
                    row.evidence.append(
                        SkillEvidence(f, titles.get(f.document_id, "Document"), origin)
                    )
                    tied.add(fid)
            linked = {e.fact.id for e in row.evidence}
            row.suggestion_count = len(self._hints(s, pool, linked, titles))
            row.goal_ids = [g for g, sid in goal_links if sid == s.id]
            rows[s.category].append(row)
        candidates = [f for f in pool if f.kind == "competency" and f.id not in tied]
        return SkillMatrix(sorted(rows.items()), LEVELS, candidates)

    # -- helpers ----------------------------------------------------------------
    def _hints(
        self, s: Skill, pool: list[Fact], linked: set[str], titles: dict[str, str]
    ) -> list[EvidenceHint]:
        query = self._query(s)
        candidates = [f for f in pool if f.id not in linked]
        meaning: dict[str, float] = {}
        if self._meaning is not None:
            meaning = meaning_matches(
                self._meaning.similarities(
                    query, {f.id: f.statement for f in candidates}, cached_only=True
                )
            )
        out = []
        for f in candidates:
            m = match_score(query, f"{f.statement} {f.quote}")
            words = m if m and len(m.shared) >= MIN_SHARED else None
            sim = meaning.get(f.id)
            if words is None and sim is None:
                continue
            out.append(
                EvidenceHint(
                    f,
                    titles.get(f.document_id, "Document"),
                    max(words.score if words else 0.0, sim or 0.0),
                    words.shared if words else (),
                    sim,
                )
            )
        out.sort(key=lambda h: (-h.score, -len(h.shared)))
        return out[:5]

    @staticmethod
    def _pool(uow: UnitOfWork) -> list[Fact]:
        return [f for k in EVIDENCE_KINDS for f in uow.facts.find(kind=k, status="accepted")]

    @staticmethod
    def _titles(uow: UnitOfWork) -> dict[str, str]:
        return {d.id: d.title for d in uow.documents.find()}

    @staticmethod
    def _latest(uow: UnitOfWork) -> dict[str, Rating]:
        out: dict[str, Rating] = {}
        for r in uow.skills.ratings():
            out[r.skill_id] = r
        return out

    @staticmethod
    def _require(uow: UnitOfWork, skill_id: str) -> Skill:
        s = uow.skills.get(skill_id)
        if s is None:
            raise NotFoundError("skill", skill_id)
        return s
