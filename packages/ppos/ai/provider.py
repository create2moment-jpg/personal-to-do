"""Local LLM providers (Ollama, vLLM / OpenAI-compatible) behind one port.

Local-first: the base URL must be a loopback address unless remote use is
explicitly allowed. There is no cloud fallback.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
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
            "Local AI is not configured. Start Ollama and set PPOS_LLM_PROVIDER=ollama "
            "and PPOS_LLM_MODEL (see Settings → Local AI)."
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
        self, base_url: str, model: str, timeout: float, allow_remote: bool = False
    ) -> None:
        _check_local(base_url, allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(  # noqa: S310 - scheme/host validated in __init__
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                data: dict[str, Any] = json.loads(resp.read())
                return data
        except urllib.error.HTTPError as exc:
            raise AIUnavailableError(
                f"local model returned HTTP {exc.code}: {exc.read()[:200]!r}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AIUnavailableError(
                f"cannot reach the local model at {self.base_url}: {exc}"
            ) from exc

    def _get_ok(self, path: str) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}{path}", timeout=2):  # noqa: S310
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
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


class OpenAICompatibleProvider(_HttpProvider):
    """vLLM, llama.cpp server, LM Studio … (OpenAI chat completions API)."""

    name = "openai_compatible"

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult:
        start = time.perf_counter()
        data = self._post(
            "/v1/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        choices = data.get("choices") or [{}]
        text = str(choices[0].get("message", {}).get("content", ""))
        return LLMResult(text, self.model, int((time.perf_counter() - start) * 1000))

    def reachable(self) -> bool:
        return self._get_ok("/v1/models")


def build_provider(
    kind: str, base_url: str, model: str, timeout: float, allow_remote: bool
) -> LLMProvider:
    if kind in ("", "none") or not model:
        return DisabledProvider()
    if kind == "ollama":
        return OllamaProvider(base_url or "http://127.0.0.1:11434", model, timeout, allow_remote)
    if kind in ("vllm", "openai_compatible"):
        return OpenAICompatibleProvider(
            base_url or "http://127.0.0.1:8000", model, timeout, allow_remote
        )
    raise AIUnavailableError(f"unknown LLM provider {kind!r} (use ollama or openai_compatible)")
