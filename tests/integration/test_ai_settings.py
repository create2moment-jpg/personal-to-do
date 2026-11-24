import importlib.util
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ppos.ai.provider import AIOutputError, OpenAICompatibleProvider, normalize_openai_base
from ppos.ai.runtime import LLMConfig
from ppos.application.book import IMPROVE_STYLES
from ppos.bootstrap import build_container
from ppos.domain.book import NodeKind
from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError

_spec = importlib.util.spec_from_file_location(
    "fake_llm", Path(__file__).parents[2] / "scripts" / "fake_llm.py"
)
assert _spec and _spec.loader
fake_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_llm)

SEEN_AUTH: list[str | None] = []


class RecordingHandler(fake_llm.Handler):  # type: ignore[name-defined, misc]
    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        SEEN_AUTH.append(self.headers.get("Authorization"))
        super().do_POST()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    SEEN_AUTH.clear()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def cfg(url: str, **kw: object) -> LLMConfig:
    return LLMConfig(enabled=True, preset="llamacpp", base_url=url, **kw)  # type: ignore[arg-type]


def test_normalize_base_url() -> None:
    assert normalize_openai_base("http://127.0.0.1:8080") == "http://127.0.0.1:8080/v1"
    assert normalize_openai_base("http://127.0.0.1:8080/v1/") == "http://127.0.0.1:8080/v1"
    assert (
        normalize_openai_base("http://127.0.0.1:8080/v1/chat/completions")
        == "http://127.0.0.1:8080/v1"
    )
    assert normalize_openai_base("http://localhost:9/custom/api") == "http://localhost:9/custom/api"


def test_test_connection_auto_detects_model_and_does_not_apply(
    settings: Settings, clock: FixedClock, server: str
) -> None:
    c = build_container(settings, clock)
    assert c.ai.name == "none" and c.ai.source == "env"
    report = c.ai.test(cfg(f"{server}/v1"))
    assert report.ok and report.model == "fake-llm" and report.reply == "OK"
    assert report.models == ["fake-llm"] and [ch.name for ch in report.checks] == ["models", "chat"]
    assert c.ai.name == "none"  # testing never changes the active settings


def test_apply_is_live_persistent_and_keeps_keys_off_disk(
    settings: Settings, clock: FixedClock, server: str
) -> None:
    c = build_container(settings, clock)
    c.ai.apply(cfg(server, temperature=0.1, max_tokens=2048), api_key="sk-secret-123")
    assert c.ai.name == "openai_compatible" and c.ai.key_source == "session"
    assert c.ai.config.base_url == f"{server}/v1"
    # live: the Prompt Book uses the new provider immediately, sending the key as a bearer token
    book = c.book.create_book("B")
    page = c.book.create_node(book.id, NodeKind.PAGE, "P", body="refactor the parser")
    assert c.book.improve(page.id, next(iter(IMPROVE_STYLES)))
    assert SEEN_AUTH[-1] == "Bearer sk-secret-123"
    # persisted without the key; a restart reloads the settings but not the key
    raw = settings.db_path.read_bytes()
    assert b"sk-secret-123" not in raw
    c2 = build_container(settings, clock)
    assert c2.ai.source == "app" and c2.ai.config.max_tokens == 2048 and c2.ai.key_source == "none"
    assert c2.ai.generation_params(0.3, 1200) == (0.1, 2048)


def test_key_from_environment_variable(
    settings: Settings, clock: FixedClock, server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MY_LLM_KEY", "env-key")
    c = build_container(settings, clock)
    c.ai.apply(cfg(server, api_key_env="MY_LLM_KEY"))
    assert c.ai.key_source == "env"
    c.ai.generate("s", "Reply with exactly: OK", temperature=0, max_tokens=20)
    assert SEEN_AUTH[-1] == "Bearer env-key"


def test_refusals_and_validation(settings: Settings, clock: FixedClock) -> None:
    c = build_container(settings, clock)
    with pytest.raises(ValidationError, match="non-local"):
        c.ai.apply(cfg("https://api.example.com/v1"))
    assert c.ai.name == "none"  # nothing changed
    report = c.ai.test(cfg("https://api.example.com/v1"))
    assert not report.ok and "non-local" in report.error
    with pytest.raises(ValidationError):
        c.ai.apply(cfg("http://127.0.0.1:8080/v1", max_tokens=40000, context_limit=32768))
    with pytest.raises(ValidationError):
        c.ai.apply(cfg("http://127.0.0.1:8080/v1", api_key_env="bad name"))
    unreachable = c.ai.test(cfg("http://127.0.0.1:9/v1", timeout_seconds=2))
    assert not unreachable.ok and "cannot reach" in unreachable.error


def test_reasoning_model_out_of_tokens_is_explained() -> None:
    class Thinking(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps(
                {
                    "model": "qwen3",
                    "choices": [
                        {
                            "message": {"content": "", "reasoning_content": "Let me think…"},
                            "finish_reason": "length",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    seen: dict[str, object] = {}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Thinking)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        p = OpenAICompatibleProvider(
            f"http://127.0.0.1:{srv.server_port}/v1", "qwen3", 5, reasoning_effort="low"
        )
        with pytest.raises(AIOutputError, match="Max output tokens"):
            p.generate("s", "u", temperature=0, max_tokens=32)
        assert seen["reasoning_effort"] == "low" and seen["max_tokens"] == 32
    finally:
        srv.shutdown()


def test_context_limit_guard(settings: Settings, clock: FixedClock, server: str) -> None:
    c = build_container(settings, clock)
    c.ai.apply(cfg(server, max_tokens=400, context_limit=600))
    with pytest.raises(AIOutputError, match="context limit"):
        c.ai.generate("s", "x" * 5000, temperature=0, max_tokens=400)


def test_ai_settings_api(client: TestClient, server: str) -> None:
    state = client.get("/api/ai/config").json()
    assert state["config"]["enabled"] is False and state["key_source"] == "none"
    assert state["presets"]["llamacpp"] == "http://127.0.0.1:8080/v1"
    body = state["config"] | {"enabled": True, "base_url": f"{server}/v1", "api_key": "sk-x"}
    t = client.post("/api/ai/test", json=body).json()
    assert t["ok"] and t["model"] == "fake-llm" and "sk-x" not in json.dumps(t)
    r = client.put("/api/ai/config", json=body)
    assert r.status_code == 200 and "sk-x" not in r.text
    assert r.json()["key_source"] == "session" and r.json()["active"]["model"] == "fake-llm"
    assert client.get("/api/ai/status").json()["enabled"] is True
    bad = client.put("/api/ai/config", json=body | {"base_url": "https://api.example.com/v1"})
    assert bad.status_code == 422
    off = client.put(
        "/api/ai/config", json=body | {"enabled": False, "clear_key": True, "api_key": None}
    )
    assert off.json()["key_source"] == "none" and off.json()["active"]["provider"] == "none"
