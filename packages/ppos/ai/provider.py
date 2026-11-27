"""Local LLM providers (Ollama, vLLM / OpenAI-compatible) behind one port.

Local-first: the base URL must be a loopback address unless remote use is
explicitly allowed. There is no cloud fallback.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from ppos.shared.errors import PposError

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}


class AIUnavailableError(PposError):
    """No local model is configured or it cannot be reached."""


class AIOutputError(PposError):
    """The model answered, but the output failed validation."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    latency_ms: int


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult: ...

    def reachable(self) -> bool: ...


class DisabledProvider:
    name = "none"
    model = ""

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult:
        raise AIUnavailableError(
            "Local AI is off. Start your local model server (llama.cpp, vLLM, Ollama, "
            "LM Studio) and turn it on in Settings → Local AI."
        )

    def reachable(self) -> bool:
        return False


def _check_local(base_url: str, allow_remote: bool) -> None:
    host = urlparse(base_url).hostname or ""
    if host not in LOOPBACK_HOSTS and not allow_remote:
        raise AIUnavailableError(
            f"Refusing non-local AI endpoint {host!r}. Private data stays on this machine; "
            "set PPOS_LLM_ALLOW_REMOTE=true only for a trusted host you control."
        )


class _HttpProvider:
    name = "http"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        allow_remote: bool = False,
        api_key: str | None = None,
    ) -> None:
        _check_local(base_url, allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._api_key = api_key or None  # never logged, never persisted

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _request(self, path: str, payload: dict[str, Any] | None, timeout: float) -> Any:
        req = urllib.request.Request(  # noqa: S310 - scheme/host validated in __init__
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=self._headers(),
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            hint = " — check the API key" if exc.code in (401, 403) else ""
            raise AIUnavailableError(
                f"model server returned HTTP {exc.code}{hint}: {exc.read()[:200]!r}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AIUnavailableError(f"cannot reach the model at {self.base_url}: {exc}") from exc
        except ValueError as exc:
            raise AIUnavailableError(f"{self.base_url}{path} did not answer with JSON") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._request(path, payload, self.timeout)
        return data if isinstance(data, dict) else {}

    def _get_ok(self, path: str) -> bool:
        try:
            self._request(path, None, 2)
            return True
        except AIUnavailableError:
            return False


class OllamaProvider(_HttpProvider):
    name = "ollama"

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult:
        start = time.perf_counter()
        data = self._post(
            "/api/chat",
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
        )
        text = str(data.get("message", {}).get("content", ""))
        return LLMResult(text, self.model, int((time.perf_counter() - start) * 1000))

    def reachable(self) -> bool:
        return self._get_ok("/api/tags")


def normalize_openai_base(url: str) -> str:
    """Accept '…:8080', '…:8080/v1' or a pasted '…/v1/chat/completions'; return '…/v1'."""
    url = url.strip().rstrip("/")
    for tail in ("/chat/completions", "/completions", "/models"):
        if url.endswith(tail):
            url = url[: -len(tail)]
    return url if urlparse(url).path not in ("", "/") else url + "/v1"


class OpenAICompatibleProvider(_HttpProvider):
    """llama.cpp server, vLLM, LM Studio, Ollama's /v1 … (OpenAI chat completions API).

    ``base_url`` ends in /v1; requests go to {base_url}/chat/completions. An empty
    model means "whatever the server serves" (the first entry of /models).
    """

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        allow_remote: bool = False,
        api_key: str | None = None,
        reasoning_effort: str = "",
    ) -> None:
        super().__init__(normalize_openai_base(base_url), model, timeout, allow_remote, api_key)
        self.reasoning_effort = reasoning_effort

    def list_models(self) -> list[str]:
        data = self._request("/models", None, min(self.timeout, 10))
        items = data.get("data", []) if isinstance(data, dict) else []
        return [str(m["id"]) for m in items if isinstance(m, dict) and m.get("id")]

    def _resolve_model(self) -> str:
        if not self.model:
            models = self.list_models()
            if not models:
                raise AIUnavailableError("the server lists no models — set a model name")
            self.model = models[0]
        return self.model

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult:
        start = time.perf_counter()
        payload: dict[str, Any] = {
            "model": self._resolve_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        data = self._post("/chat/completions", payload)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = str(message.get("content") or "")
        if not text.strip() and (
            message.get("reasoning_content") or choice.get("finish_reason") == "length"
        ):
            raise AIOutputError(
                "the model used all output tokens while reasoning and gave no answer — "
                "raise Max output tokens or lower Reasoning effort in Settings → Local AI"
            )
        model = str(data.get("model") or self.model)
        return LLMResult(text, model, int((time.perf_counter() - start) * 1000))

    def stream(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> Iterator[str]:
        """Yield answer text as the server produces it (server-sent events).

        Reasoning tokens (``reasoning_content``) are not yielded: only the answer.
        """
        payload: dict[str, Any] = {
            "model": self._resolve_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        req = urllib.request.Request(  # noqa: S310 - scheme/host validated in __init__
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    choice = (event.get("choices") or [{}])[0]
                    piece = (choice.get("delta") or {}).get("content")
                    if piece:
                        yield str(piece)
        except urllib.error.HTTPError as exc:
            hint = " — check the API key" if exc.code in (401, 403) else ""
            raise AIUnavailableError(
                f"model server returned HTTP {exc.code}{hint}: {exc.read()[:200]!r}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AIUnavailableError(f"cannot reach the model at {self.base_url}: {exc}") from exc

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Vectors from the server's /embeddings endpoint (llama.cpp needs --embeddings)."""
        data = self._post("/embeddings", {"model": model, "input": texts})
        items = sorted(data.get("data") or [], key=lambda d: d.get("index", 0))
        vectors = [[float(x) for x in d.get("embedding", [])] for d in items]
        if len(vectors) != len(texts) or not all(vectors):
            raise AIOutputError("the embeddings endpoint returned no vectors")
        return vectors

    def reachable(self) -> bool:
        return self._get_ok("/models")


def build_provider(
    kind: str, base_url: str, model: str, timeout: float, allow_remote: bool
) -> LLMProvider:
    if kind in ("", "none") or (kind == "ollama" and not model):
        return DisabledProvider()
    if kind == "ollama":
        return OllamaProvider(base_url or "http://127.0.0.1:11434", model, timeout, allow_remote)
    if kind in ("vllm", "openai_compatible"):
        return OpenAICompatibleProvider(
            base_url or "http://127.0.0.1:8080/v1", model, timeout, allow_remote
        )
    raise AIUnavailableError(f"unknown LLM provider {kind!r} (use ollama or openai_compatible)")
