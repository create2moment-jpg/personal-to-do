import json

import pytest

from ppos.application.facts import FactService
from ppos.bootstrap import Container, build_container
from ppos.domain.facts import is_grounded, parse_candidates
from ppos.infrastructure.config import Settings
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ConflictError, ValidationError
from tests.pdfgen import make_pdf

REVIEW = [
    ["Summary", "Strong ownership of the retrieval platform."],
    [
        "2. Achievements",
        "Led the hybrid retrieval benchmark adopted by two teams.",
        "Improved recall at 10 by 11 percent.",
    ],
]


def fake_runner(calls: list[dict[str, str]]):
    def run(path: str, values: dict[str, str]) -> tuple[str, str, str, int]:
        calls.append(values)
        passage = values["passage"]
        import re

        sentences = [
            x for x in re.split(r"(?<=[.!?])\s+", " ".join(passage.split())) if len(x) > 15
        ]
        first = sentences[0] if sentences else passage
        items = [
            {"kind": "achievement", "statement": first, "quote": first, "confidence": 1.4},
            {
                "kind": "achievement",
                "statement": "Invented",
                "quote": "received a promotion to staff",
                "confidence": 0.9,
            },
            {"kind": "not_a_kind", "statement": "x", "quote": first, "confidence": 0.5},
        ]
        return (
            "```json\n" + json.dumps(items) + "\n```",
            "qwen-test",
            "documents.extract_facts@v1",
            5,
        )

    return run


@pytest.fixture
def c(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock, jobs=InlineJobRunner())


def test_grounding_and_parsing() -> None:
    passage = "Led the “hybrid retrieval” benchmark adopted by two teams."
    assert is_grounded('led the "hybrid retrieval" benchmark', passage)
    assert not is_grounded("won an award", passage)
    assert not is_grounded("Led", passage)  # too short to count as evidence
    assert parse_candidates("not json") == []
    raw = '[{"kind":"Achievement","statement":"s","quote":"q q q q q","confidence":"bad"}]'
    got = parse_candidates("<think>x</think>" + raw)
    assert got[0].kind == "achievement" and got[0].confidence == 0.5


def test_extraction_keeps_only_grounded_facts_with_provenance(
    c: Container, clock: FixedClock
) -> None:
    doc = c.documents.ingest("review.pdf", make_pdf(REVIEW), kind="performance_report").document
    calls: list[dict[str, str]] = []
    svc = FactService(c.uow, clock, fake_runner(calls), InlineJobRunner())
    run = svc.start(doc.id)
    s = svc.summary(doc.id)
    assert s.run is not None and s.run.status == "done" and s.run.id == run.id
    assert s.run.facts_dropped >= 2 and len(calls) == s.run.chunks_total
    assert s.facts and all(f.status == "proposed" and f.model == "qwen-test" for f in s.facts)
    f = next(f for f in s.facts if f.page == 2)
    assert f.chunk_id and "Led the hybrid" in f.quote and f.confidence == 1.0
    assert calls[0]["doc_kind"] == "performance report"
    accepted = svc.review(f.id, "accepted", statement="Led cross-team benchmark")
    assert accepted.status == "accepted" and "Led the hybrid" in accepted.quote  # quote immutable
    assert [x.id for x in svc.find(status="accepted")] == [f.id]
    svc.start(doc.id)  # re-run replaces proposals but keeps reviewed facts
    assert any(x.id == f.id for x in svc.summary(doc.id).facts)
    with pytest.raises(ValidationError):
        svc.find(kind="nonsense")


def test_extraction_requires_ai_and_ready_document(c: Container, clock: FixedClock) -> None:
    from ppos.ai.provider import AIUnavailableError

    doc = c.documents.ingest("a.txt", b"Some text about owning the platform roadmap.").document
    with pytest.raises(AIUnavailableError):
        c.facts.start(doc.id)  # container has no AI configured

    def failing(path: str, values: dict[str, str]) -> tuple[str, str, str, int]:
        raise AIUnavailableError("model went away")

    svc = FactService(c.uow, clock, failing, InlineJobRunner())
    svc.start(doc.id)
    run = svc.summary(doc.id).run
    assert run is not None and run.status == "failed" and "went away" in (run.error or "")
    scan = c.documents.ingest("scan.pdf", make_pdf([[]])).document
    with pytest.raises(ValidationError):
        svc.start(scan.id)


def test_concurrent_runs_rejected(c: Container, clock: FixedClock) -> None:
    doc = c.documents.ingest(
        "a.txt", b"Owns the evaluation harness for retrieval quality."
    ).document

    class Deferred:
        def submit(self, name: str, fn: object) -> None:
            pass

        def wait_idle(self, timeout: float = 30) -> None:
            pass

    svc = FactService(c.uow, clock, fake_runner([]), Deferred())
    svc.start(doc.id)
    with pytest.raises(ConflictError):
        svc.start(doc.id)


def test_rerun_never_reproposes_decided_facts(c: Container, clock: FixedClock) -> None:
    doc = c.documents.ingest("review.pdf", make_pdf(REVIEW), kind="performance_report").document
    svc = FactService(c.uow, clock, fake_runner([]), InlineJobRunner())
    svc.start(doc.id)
    first = svc.summary(doc.id).facts
    svc.review(first[0].id, status="accepted")
    svc.review(first[1].id, status="rejected")
    svc.start(doc.id)
    again = svc.summary(doc.id).facts
    assert len(again) == len(first)  # no duplicates of decided facts
    assert {f.status for f in again if f.id in (first[0].id, first[1].id)} == {
        "accepted",
        "rejected",
    }
