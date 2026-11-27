import importlib.util
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ppos.ai.provider import AIUnavailableError
from ppos.ai.runtime import LLMConfig
from ppos.bootstrap import Container, build_container
from ppos.domain.assistant import check_answer, parse_day_plan, rrf
from ppos.domain.notes import NoteKind
from ppos.domain.tasks import Priority
from ppos.infrastructure.config import Settings
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.shared.clock import FixedClock

_spec = importlib.util.spec_from_file_location(
    "fake_llm", Path(__file__).parents[2] / "scripts" / "fake_llm.py"
)
assert _spec and _spec.loader
fake_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_llm)


class Quiet(fake_llm.Handler):  # type: ignore[name-defined, misc]
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


@pytest.fixture
def c(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock, jobs=InlineJobRunner())


def _seed(c: Container) -> None:
    c.notes.create(
        title="Pairing with Ana",
        body="I mentored Ana through her first design review in October.",
        kind=NoteKind.GENERAL,
    )
    c.notes.create(
        title="Retro",
        body="The ADR for hybrid retrieval is still in progress.",
        kind=NoteKind.GENERAL,
    )


def test_domain_helpers() -> None:
    assert next(k for k, _ in rrf([["a", "b"], ["b", "c"]])) == "b"
    chk = check_answer("Yes [1]. Also [3] and [1].", 2)
    assert chk.cited == [1] and chk.invalid == [3] and not chk.grounded
    assert check_answer("No citations", 2).grounded is False
    plan, dropped = parse_day_plan(
        '{"top": [{"id": "a", "why": "x"}, "zzz", "b", "c", "d"], "note": "n"}',
        {"a", "b", "c", "d"},
    )
    assert plan.top == ["a", "b", "c"] and dropped == ["zzz"] and plan.reasons["a"] == "x"


def test_keyword_search_works_without_ai(c: Container) -> None:
    _seed(c)
    sources, semantic = c.assistant.search("design review")
    assert sources[0].title == "Pairing with Ana" and sources[0].via == ["keyword"] and not semantic
    assert sources[0].link.startswith("notes/")
    with pytest.raises(AIUnavailableError):
        c.assistant.ask("Who did I mentor?")
    assert c.assistant.status().model == ""


def test_meaning_search_ask_and_plan(c: Container, server: str) -> None:
    _seed(c)
    c.ai.apply(LLMConfig(enabled=True, base_url=server, embedding_model="fake-embed"))
    assert c.assistant.index() >= 2
    assert c.assistant.index() == 0  # unchanged items are not embedded again
    st = c.assistant.status()
    assert st.model == "fake-embed" and st.indexed == st.total

    # "coaching" never appears in the note — only search by meaning finds it
    sources, semantic = c.assistant.search("coaching juniors")
    assert (
        semantic
        and sources
        and sources[0].title == "Pairing with Ana"
        and "meaning" in sources[0].via
    )

    answer = c.assistant.ask("Who did I mentor in October?")
    assert answer.grounded and answer.cited == [1] and answer.sources[0].n == 1
    assert "[1]" in answer.text and answer.model == "fake-llm"

    t1 = c.tasks.create(
        "Draft the ADR", scheduled_date=c.clock.today(), priority=Priority.P1, estimate_minutes=90
    )
    t2 = c.tasks.create("Review PR #482", scheduled_date=c.clock.today(), estimate_minutes=30)
    proposal = c.assistant.plan_day()
    assert set(proposal.plan.top) <= {t1.id, t2.id} and proposal.dropped == ["not-a-real-task"]
    assert c.days.today_view().plan.top_priority_ids == []  # nothing changes until approved
    c.assistant.apply_plan(c.clock.today(), proposal.plan.top)
    assert c.days.today_view().plan.top_priority_ids == proposal.plan.top


def test_assistant_api(client: TestClient) -> None:
    client.post(
        "/api/notes",
        json={"title": "Budget", "body": "Q1 budget approved for two GPUs", "kind": "general"},
    )
    st = client.get("/api/assistant/status").json()
    assert st["model"] == "" and st["ai"] is False
    r = client.get("/api/assistant/search", params={"q": "GPU budget"}).json()
    assert r["sources"][0]["title"] == "Budget" and r["semantic"] is False
    assert (
        client.post("/api/assistant/ask", json={"question": "What was approved?"}).status_code
        == 503
    )
    assert client.post("/api/assistant/index").status_code == 422
    assert (
        client.post(
            "/api/assistant/plan-day/apply", json={"day": "2026-11-24", "top": ["x"]}
        ).status_code
        == 422
    )


def test_questions_still_match_keywords(c: Container) -> None:
    _seed(c)
    sources, _ = c.assistant.search("What did I decide about hybrid retrieval?")
    assert sources and sources[0].title == "Retro" and "keyword" in sources[0].via
    from ppos.domain.assistant import keyword_terms

    assert keyword_terms("What did I decide about the ADR for hybrid retrieval?") == [
        "adr",
        "hybrid",
        "retrieval",
    ]
