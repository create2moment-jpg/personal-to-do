"""AI fact extraction: bounded, provenance-carrying, verbatim-grounded, user-approved."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from ppos.application.documents import JobRunner
from ppos.application.ports import UnitOfWorkFactory
from ppos.domain.documents import DocStatus
from ppos.domain.facts import FACT_KINDS, Fact, FactRun, is_grounded, parse_candidates
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError

log = logging.getLogger("ppos.facts")
MAX_CHUNKS_PER_RUN = 60

# (template path, values) -> (text, model, template ref, latency ms)
TemplateRunner = Callable[[str, dict[str, str]], tuple[str, str, str, int]]
EXTRACT_TEMPLATE = "10_documents/extract_facts/v1.md"


def _norm(quote: str) -> str:
    return " ".join(quote.lower().split())


@dataclass
class FactSummary:
    run: FactRun | None
    facts: list[Fact]


class FactService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        run_template: TemplateRunner | None,
        jobs: JobRunner,
        enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._run = run_template
        self._jobs = jobs
        self._enabled = enabled  # AI can be switched on/off at runtime

    def start(self, document_id: str) -> FactRun:
        if self._run is None or not self._enabled():
            from ppos.ai.provider import AIUnavailableError

            raise AIUnavailableError(
                "Local AI is not configured — fact extraction needs a local model."
            )
        with self._uow() as uow:
            doc = uow.documents.get(document_id)
            if doc is None:
                raise NotFoundError("document", document_id)
            if doc.status != DocStatus.READY:
                raise ValidationError("the document has no extracted text yet")
            latest = uow.facts.latest_run(document_id)
            if latest and latest.status in ("queued", "running"):
                raise ConflictError("an extraction is already running for this document")
            total = min(len(uow.documents.chunks(document_id)), MAX_CHUNKS_PER_RUN)
            run = FactRun(new_id(), document_id, "queued", self._clock.now(), chunks_total=total)
            uow.facts.add_run(run)
            uow.commit()
        self._jobs.submit(f"extract-facts-{document_id}", lambda: self._execute(run.id))
        return run

    def _execute(self, run_id: str) -> None:
        assert self._run is not None
        with self._uow() as uow:
            run = uow.facts.get_run(run_id)
            assert run is not None
            doc = uow.documents.get(run.document_id)
            chunks = uow.documents.chunks(run.document_id)[:MAX_CHUNKS_PER_RUN]
            run.status = "running"
            uow.facts.update_run(run)
            uow.facts.delete_proposed(run.document_id)  # re-run replaces earlier proposals
            # Facts the user already accepted or rejected are never proposed again.
            decided = {
                (f.kind, _norm(f.quote)) for f in uow.facts.find(document_id=run.document_id)
            }
            uow.commit()
        if doc is None:
            return
        found = dropped = 0
        try:
            for ch in chunks:
                section = f", section: {ch['section']}" if ch.get("section") else ""
                text, model, template, _ = self._run(
                    EXTRACT_TEMPLATE,
                    {
                        "doc_kind": doc.kind.replace("_", " "),
                        "page": str(ch.get("page_start") or "?"),
                        "section_note": section,
                        "passage": str(ch["text"]),
                    },
                )
                now = self._clock.now()
                with self._uow() as uow:
                    for cand in parse_candidates(text):
                        if not is_grounded(cand.quote, str(ch["text"])):
                            dropped += 1  # quote not in the source: never stored
                            continue
                        if (cand.kind, _norm(cand.quote)) in decided:
                            continue
                        decided.add((cand.kind, _norm(cand.quote)))
                        found += 1
                        uow.facts.add(
                            Fact(
                                id=new_id(),
                                document_id=doc.id,
                                kind=cand.kind,
                                statement=cand.statement,
                                quote=cand.quote,
                                confidence=cand.confidence,
                                model=model,
                                prompt_template=template,
                                created_at=now,
                                updated_at=now,
                                chunk_id=str(ch["id"]),
                                run_id=run_id,
                                page=ch["page_start"]
                                if isinstance(ch.get("page_start"), int)
                                else None,  # type: ignore[arg-type]
                                section=str(ch["section"]) if ch.get("section") else None,
                                extractor_version=str(ch.get("extractor_version") or ""),
                            )
                        )
                    r = uow.facts.get_run(run_id)
                    assert r is not None
                    r.chunks_done += 1
                    r.facts_found, r.facts_dropped, r.model, r.prompt_template = (
                        found,
                        dropped,
                        model,
                        template,
                    )
                    uow.facts.update_run(r)
                    uow.commit()
            status, error = "done", None
        except Exception as exc:  # AI unavailable mid-run, timeouts …
            log.warning("fact extraction %s failed: %s", run_id, exc)
            status, error = "failed", str(exc)[:500]
        with self._uow() as uow:
            r = uow.facts.get_run(run_id)
            assert r is not None
            r.status, r.error, r.finished_at = status, error, self._clock.now()
            uow.facts.update_run(r)
            uow.audit.record(
                "document",
                r.document_id,
                "extract_facts",
                actor="ai",
                details={
                    "found": found,
                    "dropped_ungrounded": dropped,
                    "model": r.model,
                    "template": r.prompt_template,
                },
            )
            uow.commit()

    def summary(self, document_id: str) -> FactSummary:
        with self._uow() as uow:
            return FactSummary(
                uow.facts.latest_run(document_id), uow.facts.find(document_id=document_id)
            )

    def find(self, kind: str | None = None, status: str | None = None) -> list[Fact]:
        if kind is not None and kind not in FACT_KINDS:
            raise ValidationError(f"kind must be one of {', '.join(FACT_KINDS)}")
        with self._uow() as uow:
            return uow.facts.find(kind=kind, status=status)

    def review(
        self,
        fact_id: str,
        status: str | None = None,
        statement: str | None = None,
        note: str | None = None,
    ) -> Fact:
        if status is not None and status not in ("proposed", "accepted", "rejected"):
            raise ValidationError("status must be proposed, accepted or rejected")
        with self._uow() as uow:
            f = uow.facts.get(fact_id)
            if f is None:
                raise NotFoundError("fact", fact_id)
            if status:
                f.status = status
            if statement is not None:
                if not statement.strip():
                    raise ValidationError("statement must not be empty")
                f.statement = " ".join(
                    statement.split()
                )  # wording may change; the quote never does
            if note is not None:
                f.note = note
            f.updated_at = self._clock.now()
            uow.facts.update(f)
            uow.audit.record("fact", fact_id, "review", details={"status": f.status})
            uow.commit()
            return f
