"""Assistant: answers and proposals grounded in your own records.

Retrieval fuses keyword search (always on) with search by meaning (when an
embedding model is configured) using reciprocal-rank fusion. Answers must cite
the numbered sources they were given; plans are proposals you approve.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, tzinfo

from ppos.ai.output import clean_improved
from ppos.ai.runtime import AIRuntime
from ppos.application.daily import DayService
from ppos.application.documents import JobRunner
from ppos.application.ports import NoteQuery, TaskQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.assistant import (
    DayPlan,
    Source,
    check_answer,
    cosine_top,
    keyword_terms,
    pack,
    parse_day_plan,
    rrf,
    strip_think,
)
from ppos.domain.documents import DocStatus
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import Clock
from ppos.shared.errors import ValidationError

log = logging.getLogger("ppos.assistant")
TemplateRunner = Callable[[str, dict[str, str]], tuple[str, str, str, int]]
ASK_TEMPLATE = "13_meta/ask/v1.md"
REWRITE_TEMPLATE = "02_writing/improve_note/v1.md"
REWRITE_STYLES: dict[str, str] = {
    "clearer": "Make it clearer and easier to read: shorter sentences, plain words, logical order.",
    "shorter": "Make it about half as long: keep every fact and decision, "
    "drop repetition and filler.",
    "structure": "Give it structure: short headings where useful, bullet points for "
    "lists of items, action items as a checklist.",
    "grammar": "Only fix spelling, grammar and punctuation. Change nothing else.",
    "professional": "Make the tone professional and concise, suitable to share with colleagues.",
}
MAX_REWRITE_CHARS = 12_000
PLAN_TEMPLATE = "03_daily/plan_day/v1.md"
MAX_SOURCE_CHARS = 1500
EMBED_BATCH = 16
SEARCHABLE = ("task", "note", "page", "chunk")


@dataclass
class IndexStatus:
    model: str  # "" = search by meaning is off
    indexed: int
    total: int
    running: bool
    error: str | None = None


@dataclass
class Answer:
    question: str
    text: str
    sources: list[Source]
    cited: list[int]
    invalid: list[int]
    grounded: bool
    model: str
    semantic: bool


@dataclass
class Rewrite:
    original: str
    text: str
    style: str
    model: str
    new_numbers: list[str]  # numbers in the rewrite that the original didn't contain


def _numbers(text: str) -> list[str]:
    import re

    return [n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", text)]


@dataclass
class PlanProposal:
    day: date
    plan: DayPlan
    dropped: list[str]
    candidates: dict[str, str]  # id -> title, for display
    model: str
    capacity_minutes: int = 0
    meeting_minutes: int = 0
    current_top: list[str] = field(default_factory=list)


class AssistantService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        ai: AIRuntime,
        run_template: TemplateRunner,
        jobs: JobRunner,
        days: DayService,
        tz: Callable[[], tzinfo],
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._ai = ai
        self._run = run_template
        self._jobs = jobs
        self._days = days
        self._tz = tz
        self._indexing = False
        self._index_error: str | None = None

    # -- corpus -------------------------------------------------------------------
    def _corpus(self, uow: UnitOfWork) -> dict[str, tuple[str, str]]:
        """key -> (title, text) for everything worth searching by meaning."""
        out: dict[str, tuple[str, str]] = {}
        for n in uow.notes.find(NoteQuery(limit=5000)):
            out[f"note:{n.id}"] = (n.title, n.body)
        for b in uow.books.books():
            for node in uow.books.nodes(b.id):
                if node.body.strip():
                    out[f"page:{node.id}"] = (node.title, node.body)
        for d in uow.documents.find((DocStatus.READY,)):
            for ch in uow.documents.chunks(d.id):
                out[f"chunk:{ch['id']}"] = (d.title, str(ch["text"]))
        for t in uow.tasks.find(TaskQuery(top_level_only=True, limit=5000)):
            out[f"task:{t.id}"] = (t.title, f"{t.description}\n{t.notes}".strip())
        return out

    # -- index (search by meaning) -------------------------------------------------
    def status(self) -> IndexStatus:
        model = self._ai.embedding_model
        with self._uow() as uow:
            total = len(self._corpus(uow))
            indexed = uow.embeddings.count(model) if model else 0
        return IndexStatus(model, min(indexed, total), total, self._indexing, self._index_error)

    def start_index(self) -> IndexStatus:
        if not self._ai.embedding_model:
            raise ValidationError("set an embedding model in Settings → Local AI first")
        if not self._indexing:
            self._indexing = True
            self._jobs.submit("embed-index", self._index_job)
        return self.status()

    def _index_job(self) -> None:
        self.index()

    def index(self) -> int:
        """Embed new or changed items; drop vectors for things that no longer exist."""
        model = self._ai.embedding_model
        self._indexing, self._index_error = True, None
        done = 0
        try:
            if not model:
                return 0
            with self._uow() as uow:
                corpus = self._corpus(uow)
                known = uow.embeddings.hashes(model)
                uow.embeddings.prune(set(corpus))
                uow.commit()
            todo = []
            for key, (title, text) in corpus.items():
                body = f"{title}\n{text}"[:2000]
                h = hashlib.sha256(body.encode()).hexdigest()[:16]
                if known.get(key) != h:
                    todo.append((key, h, body))
            for i in range(0, len(todo), EMBED_BATCH):
                batch = todo[i : i + EMBED_BATCH]
                vectors = self._ai.embed([b for _, _, b in batch])
                with self._uow() as uow:
                    for (key, h, _), vec in zip(batch, vectors, strict=True):
                        uow.embeddings.put(key, model, h, len(vec), pack(vec))
                    uow.commit()
                done += len(batch)
            return done
        except Exception as exc:  # model down, endpoint not enabled …
            log.warning("embedding index stopped: %s", exc)
            self._index_error = str(exc)[:300]
            return done
        finally:
            self._indexing = False

    # -- retrieval -------------------------------------------------------------------
    def search(self, query: str, k: int = 8) -> tuple[list[Source], bool]:
        """Hybrid retrieval. Returns sources and whether search by meaning took part."""
        query = " ".join(query.split())
        if len(query) < 2:
            raise ValidationError("type at least two characters")
        terms = keyword_terms(query)
        with self._uow() as uow:
            hits = uow.search.search(" ".join(terms), 30) if terms else []
            if not hits and len(terms) > 1:  # no passage has every word: rank by any of them
                per_term = [
                    [f"{h.entity_type.value}:{h.entity_id}" for h in uow.search.search(t, 15)]
                    for t in terms
                ]
                keyword = [key for key, _ in rrf(per_term)][:30]
            else:
                keyword = [f"{h.entity_type.value}:{h.entity_id}" for h in hits]
            vectors = (
                uow.embeddings.vectors(self._ai.embedding_model) if self._ai.embedding_model else []
            )
        keyword = [kk for kk in keyword if kk.split(":")[0] in SEARCHABLE]
        meaning: list[str] = []
        if vectors:
            try:
                qv = self._ai.embed([query])[0]
                top = cosine_top(qv, vectors, 30)
                best = top[0][1] if top else 0.0
                # scores differ between embedding models: keep what is close to the best match
                cutoff = max(0.1, best * 0.6)
                meaning = [key for key, score in top if score >= cutoff]
            except Exception as exc:  # fall back to keywords only
                log.info("search by meaning unavailable: %s", exc)
        fused = [key for key, _ in rrf([keyword, meaning])][:k]
        sources = self._load(fused)
        for s in sources:
            key = f"{s.kind}:{s.id}"
            s.via = [
                name for name, lst in (("keyword", keyword), ("meaning", meaning)) if key in lst
            ]
        return sources, bool(meaning)

    def _load(self, keys: list[str]) -> list[Source]:
        out: list[Source] = []
        with self._uow() as uow:
            chunk_ids = [k.split(":", 1)[1] for k in keys if k.startswith("chunk:")]
            chunks = uow.documents.chunk_context(chunk_ids)
            for key in keys:
                kind, _, oid = key.partition(":")
                src: Source | None = None
                if kind == "note" and (n := uow.notes.get(oid)):
                    src = Source("note", oid, n.title or "Untitled note", n.body, f"notes/{oid}")
                elif kind == "page" and (p := uow.books.get_node(oid)):
                    src = Source("page", oid, p.title or "Prompt", p.body, f"book/{oid}")
                elif kind == "task" and (t := uow.tasks.get(oid)):
                    text = f"Task ({t.status.value}): {t.title}. {t.description} {t.notes}".strip()
                    src = Source("task", oid, t.title, text, f"task/{oid}")
                elif kind == "chunk" and (c := chunks.get(oid)):
                    page = f", p. {c['page_start']}" if c.get("page_start") else ""
                    src = Source(
                        "chunk",
                        oid,
                        f"{c['title']}{page}",
                        str(c.get("text", "")),
                        f"knowledge/{c['document_id']}~{oid}",
                    )
                if src is not None:
                    src.text = " ".join(src.text.split())[:MAX_SOURCE_CHARS]
                    out.append(src)
        return out

    # -- ask -----------------------------------------------------------------------------
    def ask(self, question: str) -> Answer:
        question = " ".join(question.split())
        if len(question) < 3:
            raise ValidationError("ask a question")
        if self._ai.name == "none":
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError(
                "Local AI is off — turn it on in Settings → Local AI. Search below still works."
            )
        sources, semantic = self.search(question, 8)
        if not sources:
            return Answer(
                question,
                "I couldn't find anything about that in your notes, documents, tasks or prompts.",
                [],
                [],
                [],
                False,
                "",
                semantic,
            )
        for i, s in enumerate(sources, start=1):
            s.n = i
        block = "\n\n".join(f"[{s.n}] ({s.kind}) {s.title}\n{s.text}" for s in sources)
        text, model, template, _ = self._run(
            ASK_TEMPLATE,
            {"question": question, "sources": block, "today": self._clock.today().isoformat()},
        )
        answer = strip_think(text)
        check = check_answer(answer, len(sources))
        with self._uow() as uow:
            uow.audit.record(
                "assistant",
                "ask",
                "answer",
                actor="ai",
                details={
                    "model": model,
                    "template": template,
                    "sources": len(sources),
                    "grounded": check.grounded,
                },
            )
            uow.commit()
        return Answer(
            question, answer, sources, check.cited, check.invalid, check.grounded, model, semantic
        )

    # -- writing assistant ---------------------------------------------------------------
    def rewrite(self, text: str, style: str) -> Rewrite:
        """Rewrite note text in a style; flags numbers that were not in the original."""
        if style not in REWRITE_STYLES:
            raise ValidationError(f"style must be one of {', '.join(REWRITE_STYLES)}")
        if not text.strip():
            raise ValidationError("select some text or write something first")
        if len(text) > MAX_REWRITE_CHARS:
            raise ValidationError(
                "that's long for one rewrite — select a section (up to 12,000 characters)"
            )
        if self._ai.name == "none":
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError("Local AI is off — turn it on in Settings → Local AI.")
        raw, model, template, _ = self._run(
            REWRITE_TEMPLATE, {"style_instruction": REWRITE_STYLES[style], "text": text}
        )
        out = clean_improved(raw)
        new_numbers = sorted(set(_numbers(out)) - set(_numbers(text)))
        with self._uow() as uow:
            uow.audit.record(
                "note",
                "rewrite",
                style,
                actor="ai",
                details={"model": model, "template": template, "new_numbers": len(new_numbers)},
            )
            uow.commit()
        return Rewrite(text, out, style, model, new_numbers)

    # -- plan my day -------------------------------------------------------------------
    def plan_day(self, day: date | None = None) -> PlanProposal:
        if self._ai.name == "none":
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError("Local AI is off — turn it on in Settings → Local AI.")
        day = day or self._clock.today()
        view = self._days.today_view(day)
        tz = self._tz()
        open_today = [t for t in view.tasks if t.parent_id is None and t.status != TaskStatus.DONE]
        candidates = {t.id: t for t in [*open_today, *view.overdue, *view.due_today_unscheduled]}
        if not candidates:
            raise ValidationError("nothing open for this day — plan some tasks first")
        lines = []
        for t in candidates.values():
            due = f", due {t.due_date.isoformat()}" if t.due_date else ""
            est = f", {t.estimate_minutes} min" if t.estimate_minutes else ", no estimate"
            late = " (overdue)" if t in view.overdue else ""
            lines.append(
                f"{t.id} | {t.title} | P{int(t.priority)}{est}{due}{late} | {t.status.value}"
            )
        meetings = (
            "\n".join(
                f"- {m.start_at.astimezone(tz).strftime('%H:%M')} {m.title}"
                f" ({m.duration_minutes} min)"
                for m in view.meetings
            )
            or "- none"
        )
        text, model, _template, _ = self._run(
            PLAN_TEMPLATE,
            {
                "day": day.isoformat(),
                "capacity": str(view.capacity.capacity_minutes),
                "objective": view.plan.objective or "(none set)",
                "tasks": "\n".join(lines),
                "meetings": meetings,
            },
        )
        plan, dropped = parse_day_plan(text, set(candidates))
        return PlanProposal(
            day, plan, dropped, {k: v.title for k, v in candidates.items()}, model,
            view.capacity.capacity_minutes, view.time.meeting_minutes if view.time else 0,
            list(view.plan.top_priority_ids),
        )  # fmt: skip

    def apply_plan(self, day: date, top: list[str]) -> list[str]:
        """You approved the proposal: set the day's top priorities (and plan them for that day)."""
        if len(top) > 3:
            raise ValidationError("at most three top priorities")
        with self._uow() as uow:
            for tid in top:
                t = uow.tasks.get(tid)
                if t is None:
                    raise ValidationError("a proposed task no longer exists")
        from ppos.application.tasks import TaskService

        tasks = TaskService(self._uow, self._clock)
        for tid in top:
            t = tasks.get(tid)
            if t.scheduled_date != day and t.status != TaskStatus.DONE:
                tasks.move(tid, scheduled_date=day)
        self._days.update_plan(day, {"top_priority_ids": top})
        with self._uow() as uow:
            uow.audit.record("day", day.isoformat(), "apply_ai_plan", details={"top": top})
            uow.commit()
        return top
