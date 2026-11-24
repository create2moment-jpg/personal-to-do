import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ppos.ai.output import clean_improved
from ppos.ai.prompts import load_template
from ppos.ai.provider import AIOutputError, AIUnavailableError, OllamaProvider, build_provider
from ppos.application.book import BookService
from ppos.bootstrap import Container
from ppos.domain.book import NodeKind, VersionSource, fill_variables
from ppos.infrastructure.config import REPO_ROOT
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError


def test_tree_hierarchy_and_moves(container: Container) -> None:
    b = container.book.create_book("Copilot prompts", emoji="🤖")
    ch = container.book.create_node(b.id, NodeKind.CHAPTER, "Refactoring")
    sec = container.book.create_node(b.id, NodeKind.SECTION, "Python", parent_id=ch.id)
    sub = container.book.create_node(b.id, NodeKind.SECTION, "Typing", parent_id=sec.id)
    page = container.book.create_node(
        b.id, NodeKind.PAGE, "Add type hints", parent_id=sub.id, body="Add hints to {{file}}"
    )
    with pytest.raises(ValidationError):
        container.book.create_node(b.id, NodeKind.PAGE, "x", parent_id=page.id)  # pages are leaves
    with pytest.raises(ValidationError):
        container.book.move(ch.id, sub.id)  # cycle
    moved = container.book.move(page.id, ch.id)
    assert moved.parent_id == ch.id
    _, nodes = container.book.tree(b.id)
    assert {n.title for n in nodes} == {"Refactoring", "Python", "Typing", "Add type hints"}
    container.book.delete_node(ch.id)  # cascades
    assert container.book.tree(b.id)[1] == []


def test_depth_limit(container: Container) -> None:
    b = container.book.create_book("Deep")
    parent = None
    for i in range(8):  # MAX_DEPTH levels are allowed; the 9th is refused
        parent = container.book.create_node(
            b.id, NodeKind.SECTION, f"L{i}", parent_id=parent.id if parent else None
        )
    with pytest.raises(ValidationError):
        container.book.create_node(
            b.id, NodeKind.SECTION, "too deep", parent_id=parent.id if parent else None
        )


def test_versions_use_and_restore(container: Container, clock: FixedClock) -> None:
    b = container.book.create_book("B")
    p = container.book.create_node(
        b.id, NodeKind.PAGE, "Review", body="Review {{file}} for {{concern}}"
    )
    assert p.variables == ["file", "concern"]
    container.book.update_node(p.id, {"body": "Review {{file}} for {{concern}} and tests"})
    text = container.book.use(p.id, {"file": "app.py", "concern": "races"})
    assert text == "Review app.py for races and tests"
    page = container.book.node(p.id)
    assert page.use_count == 1 and page.last_used_at is not None
    versions = container.book.versions(p.id)
    assert [v.source for v in versions] == [VersionSource.USED, VersionSource.ORIGINAL]
    restored = container.book.restore(p.id, 1)
    assert restored.body == "Review {{file}} for {{concern}}"
    assert container.book.versions(p.id)[0].source == VersionSource.RESTORED


def test_improve_keeps_original_and_accept(container: Container, clock: FixedClock) -> None:
    calls: list[tuple[str, str]] = []

    def fake(original: str, instruction: str) -> tuple[str, str, str, int]:
        calls.append((original, instruction))
        return (
            "Goal: refactor X.\nContext: [which module?]",
            "qwen-test",
            "writing.improve_prompt@v1",
            42,
        )

    svc = BookService(container.uow, clock, fake)
    b = svc.create_book("B")
    p = svc.create_node(b.id, NodeKind.PAGE, "P", body="refactor x pls")
    r = svc.improve(p.id, "clearer")
    assert r.original == "refactor x pls" and r.model == "qwen-test" and calls
    assert svc.node(p.id).body == "refactor x pls"  # not overwritten
    ai_version = svc.versions(p.id)[0]
    assert ai_version.source == VersionSource.AI and ai_version.model == "qwen-test"
    assert svc.accept(p.id, r.version).body.startswith("Goal:")
    assert any(v.body == "refactor x pls" for v in svc.versions(p.id))  # original kept
    with pytest.raises(ValidationError):
        svc.improve(p.id, "nonsense-style")


def test_improve_without_ai_is_explicit(container: Container) -> None:
    b = container.book.create_book("B")
    p = container.book.create_node(b.id, NodeKind.PAGE, "P", body="hello")
    with pytest.raises(AIUnavailableError):
        container.book.improve(p.id, "clearer")


def test_pages_are_searchable(container: Container) -> None:
    b = container.book.create_book("B")
    container.book.create_node(
        b.id, NodeKind.PAGE, "Flaky test triage", body="Find the root cause of flaky pytest runs"
    )
    hits = container.search("flaky")
    assert hits and hits[0].entity_type.value == "page"


def test_fill_variables_leaves_unknown() -> None:
    assert fill_variables("{{a}} {{ b }} {{c}}", {"a": "1", "b": "2"}) == "1 2 {{c}}"


def test_clean_improved_output() -> None:
    assert clean_improved("Here is the improved prompt:\n```\nDo X\n```") == "Do X"
    assert clean_improved("<think>hmm</think>\nDo Y") == "Do Y"
    with pytest.raises(AIOutputError):
        clean_improved("   ")


def test_template_loads_and_renders() -> None:
    t = load_template(REPO_ROOT / "prompts", "02_writing/improve_prompt/v1.md")
    assert t.ref == "writing.improve_prompt@v1"
    out = t.render(style_instruction="Be clear.", prompt="fix {{file}}")
    assert "Be clear." in out and "fix {{file}}" in out


def test_remote_endpoints_refused_by_default() -> None:
    with pytest.raises(AIUnavailableError):
        build_provider("ollama", "https://api.example.com", "m", 5, allow_remote=False)
    assert build_provider("none", "", "", 5, False).name == "none"


def test_ollama_provider_against_fake_server() -> None:
    seen: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"message": {"content": "Improved text"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        p = OllamaProvider(f"http://127.0.0.1:{server.server_port}", "qwen-test", timeout=5)
        r = p.generate("sys", "user", temperature=0.2, max_tokens=50)
        assert r.text == "Improved text" and r.model == "qwen-test"
        assert seen["model"] == "qwen-test" and seen["stream"] is False
        assert p.reachable()
    finally:
        server.shutdown()
    dead = OllamaProvider("http://127.0.0.1:9", "m", timeout=1)
    with pytest.raises(AIUnavailableError):
        dead.generate("s", "u", temperature=0, max_tokens=1)


def test_api_book_flow(client: object) -> None:
    from fastapi.testclient import TestClient

    assert isinstance(client, TestClient)
    b = client.post("/api/books", json={"title": "Prompts", "emoji": "📘"}).json()
    ch = client.post(
        "/api/book-nodes", json={"book_id": b["id"], "kind": "chapter", "title": "Tests"}
    ).json()
    pg = client.post(
        "/api/book-nodes",
        json={
            "book_id": b["id"],
            "kind": "page",
            "title": "Unit tests",
            "parent_id": ch["id"],
            "body": "Write tests for {{fn}}",
        },
    ).json()
    assert pg["variables"] == ["fn"]
    assert (
        client.post(f"/api/book-nodes/{pg['id']}/use", json={"values": {"fn": "parse"}}).json()[
            "text"
        ]
        == "Write tests for parse"
    )
    r = client.post(f"/api/book-nodes/{pg['id']}/improve", json={"style": "clearer"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]
    assert client.get("/api/ai/status").json()["enabled"] is False
    tree = client.get(f"/api/books/{b['id']}/tree").json()
    assert len(tree["nodes"]) == 2
    assert Path  # keep import used
