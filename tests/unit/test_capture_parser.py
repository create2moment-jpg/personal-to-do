from datetime import date

from ppos.domain.capture import CaptureKind, parse_capture
from ppos.domain.tasks import Priority

TUE = date(2026, 11, 24)  # a Tuesday


def test_full_task_grammar() -> None:
    p = parse_capture("Review PR #code !2 ~1h30m @tomorrow due:fri +ml-platform", TUE)
    assert p.kind == CaptureKind.TASK
    assert p.title == "Review PR"
    assert p.tags == ["code"]
    assert p.priority == Priority.P2
    assert p.estimate_minutes == 90
    assert p.scheduled_date == date(2026, 11, 25)
    assert p.due_date == date(2026, 11, 27)
    assert p.project_hint == "ml platform"


def test_weekday_is_always_next_occurrence() -> None:
    assert parse_capture("x @tue", TUE).scheduled_date == date(2026, 12, 1)
    assert parse_capture("x @2026-12-24", TUE).scheduled_date == date(2026, 12, 24)


def test_unrecognised_tokens_stay_in_title() -> None:
    p = parse_capture("email bob@example.com about ~ budget !9 @nowhere", TUE)
    assert p.title == "email bob@example.com about ~ budget !9 @nowhere"
    assert p.scheduled_date is None


def test_idea_prefix_keeps_text_verbatim() -> None:
    p = parse_capture("idea: cache embeddings per chunk ~30m #rag", TUE)
    assert p.kind == CaptureKind.IDEA
    assert p.title == "cache embeddings per chunk ~30m #rag"
    assert p.tags == ["rag"]
