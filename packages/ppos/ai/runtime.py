"""Local AI settings chosen in the app, applied live (no restart).

Non-secret settings are stored in the database. An API key is either held in
server memory for the running session (never written to disk, never returned
by the API) or read from an environment variable whose *name* is stored.
"""

from __future__ import annotations

import contextlib
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from ppos.ai.provider import (
    AIOutputError,
    AIUnavailableError,
    DisabledProvider,
    LLMProvider,
    LLMResult,
    OpenAICompatibleProvider,
    normalize_openai_base,
)
from ppos.application.ports import UnitOfWorkFactory
from ppos.shared.errors import ValidationError

PRESETS: dict[str, str] = {
    "llamacpp": "http://127.0.0.1:8080/v1",
    "vllm": "http://127.0.0.1:8000/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "custom": "",
}
REASONING_EFFORTS = ("", "low", "medium", "high")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    preset: str = "llamacpp"
    base_url: str = PRESETS["llamacpp"]
    model: str = ""  # empty: use the model the server serves
    api_key_env: str = ""
    reasoning_effort: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    context_limit: int = 32768
    timeout_seconds: float = 120

    def validated(self) -> LLMConfig:
        if self.preset not in PRESETS:
            raise ValidationError(f"preset must be one of {', '.join(PRESETS)}")
        if not re.match(r"^https?://", self.base_url.strip()):
            raise ValidationError("endpoint must start with http:// or https://")
        if self.reasoning_effort not in REASONING_EFFORTS:
            raise ValidationError("reasoning effort must be low, medium, high or empty")
        if self.api_key_env and not _ENV_NAME.match(self.api_key_env):
            raise ValidationError("API key variable must look like MY_API_KEY")
        if not 0 <= self.temperature <= 2:
            raise ValidationError("temperature must be between 0 and 2")
        if not 16 <= self.max_tokens <= 262_144:
            raise ValidationError("max output tokens must be between 16 and 262144")
        if not 512 <= self.context_limit <= 2_000_000:
            raise ValidationError("context limit must be between 512 and 2000000 tokens")
        if self.max_tokens >= self.context_limit:
            raise ValidationError("max output tokens must be smaller than the context limit")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValidationError("timeout must be between 1 and 3600 seconds")
        return replace(
            self,
            base_url=normalize_openai_base(self.base_url),
            model=self.model.strip(),
            api_key_env=self.api_key_env.strip(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Check:
    name: str
    ok: bool
    ms: int
    detail: str = ""


@dataclass
class TestReport:
    ok: bool
    model: str = ""
    latency_ms: int = 0
    reply: str = ""
    error: str = ""
    models: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class AIRuntime:
    """The app's single LLM provider; reconfigurable while the server runs."""

    def __init__(
        self,
        uow: UnitOfWorkFactory,
        env_default: LLMConfig,
        allow_remote: bool,
        env_provider: LLMProvider | None = None,
    ) -> None:
        self._uow = uow
        self._allow_remote = allow_remote
        self._lock = threading.Lock()
        self._session_key: str | None = None
        with uow() as u:
            stored = u.settings.ai_config()
        self.source = "app" if stored else "env"
        self._config = LLMConfig.from_dict(stored) if stored else env_default
        # A legacy .env Ollama setup keeps its native provider until the user applies app settings.
        self._provider = (
            env_provider if (env_provider and not stored) else self._build(self._config)
        )

    # -- configuration ------------------------------------------------------
    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def key_source(self) -> str:
        if self._session_key:
            return "session"
        if self._config.api_key_env and os.environ.get(self._config.api_key_env):
            return "env"
        return "none"

    def _key(self, session_key: str | None, cfg: LLMConfig) -> str | None:
        if session_key:
            return session_key
        return os.environ.get(cfg.api_key_env) if cfg.api_key_env else None

    def _build(self, cfg: LLMConfig, session_key: str | None = None) -> LLMProvider:
        if not cfg.enabled:
            return DisabledProvider()
        return OpenAICompatibleProvider(
            cfg.base_url,
            cfg.model,
            cfg.timeout_seconds,
            self._allow_remote,
            api_key=self._key(session_key or self._session_key, cfg),
            reasoning_effort=cfg.reasoning_effort,
        )

    def apply(self, cfg: LLMConfig, api_key: str | None = None, clear_key: bool = False) -> None:
        cfg = cfg.validated()
        with self._lock:
            if clear_key:
                self._session_key = None
            if api_key:
                self._session_key = api_key.strip()
            try:  # a non-local endpoint is refused before anything changes
                provider = self._build(cfg)
            except AIUnavailableError as exc:
                raise ValidationError(str(exc)) from exc
            with self._uow() as u:
                u.settings.set_ai_config(asdict(cfg))
                u.audit.record(
                    "settings",
                    "ai",
                    "update",
                    details={k: v for k, v in asdict(cfg).items() if k != "api_key_env"},
                )
                u.commit()
            self._config, self._provider, self.source = cfg, provider, "app"
        self.detect_model()

    def detect_model(self) -> str:
        """Fill in the served model when none is set; never fails (the server may be down)."""
        p = self._provider
        if isinstance(p, OpenAICompatibleProvider) and not p.model:
            with contextlib.suppress(AIUnavailableError):
                p.model = (p.list_models() or [""])[0]
        return p.model

    def test(self, cfg: LLMConfig, api_key: str | None = None) -> TestReport:
        """Try a configuration without applying it: list models, then a tiny chat."""
        try:
            cfg = replace(cfg.validated(), enabled=True)
            p = self._build(cfg, api_key)
        except (ValidationError, AIUnavailableError) as exc:
            return TestReport(False, error=str(exc))
        assert isinstance(p, OpenAICompatibleProvider)
        report = TestReport(False)
        t = time.perf_counter()
        try:
            report.models = p.list_models()
            report.checks.append(Check("models", True, _ms(t), f"{len(report.models)} listed"))
        except AIUnavailableError as exc:
            report.checks.append(Check("models", False, _ms(t), str(exc)))
        t = time.perf_counter()
        try:
            r = p.generate(
                "You are a connection test.",
                "Reply with exactly: OK",
                temperature=0,
                max_tokens=min(cfg.max_tokens, 1024),
            )
            report.ok, report.model, report.latency_ms = True, r.model, r.latency_ms
            report.reply = _strip_think(r.text)[:200]
            report.checks.append(Check("chat", True, _ms(t)))
        except (AIUnavailableError, AIOutputError) as exc:
            report.error = str(exc)
            report.checks.append(Check("chat", False, _ms(t), str(exc)))
        return report

    # -- LLMProvider ----------------------------------------------------------
    @property
    def name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model or (self._config.model if self._config.enabled else "")

    def generate(
        self, system: str, prompt: str, *, temperature: float, max_tokens: int
    ) -> LLMResult:
        budget = self._config.context_limit - max_tokens
        if (
            len(system) + len(prompt)
        ) / 3.5 > budget:  # rough token estimate, errs on the safe side
            raise AIOutputError(
                "this request is larger than the model's context limit — "
                "raise Context limit in Settings → Local AI if your server allows it"
            )
        return self._provider.generate(
            system, prompt, temperature=temperature, max_tokens=max_tokens
        )

    def generation_params(self, default_temperature: float, default_max: int) -> tuple[float, int]:
        if self.source == "app":
            return self._config.temperature, self._config.max_tokens
        return default_temperature, default_max

    def reachable(self) -> bool:
        return self._provider.reachable()


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def env_config(provider: str, base_url: str, model: str, timeout: float) -> LLMConfig:
    """Translate the legacy PPOS_LLM_* environment variables into app settings."""
    if provider in ("", "none"):
        return LLMConfig(timeout_seconds=timeout)
    preset = "ollama" if provider == "ollama" else "custom"
    url = base_url or (PRESETS["ollama"] if provider == "ollama" else PRESETS["llamacpp"])
    if provider == "ollama":
        url = url.rstrip("/").removesuffix("/v1") + "/v1"
    return LLMConfig(
        enabled=True, preset=preset, base_url=url, model=model, timeout_seconds=timeout
    )
