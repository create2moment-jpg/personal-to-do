"""Local AI provider settings: read, apply live, and test a configuration.

The API key is write-only: it is accepted on apply/test, held in memory, and
never returned or logged (request bodies are never logged — threat model T9).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ppos.ai.runtime import PRESETS, LLMConfig
from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ConfigIn(BaseModel):
    enabled: bool
    preset: str = Field(max_length=20)
    base_url: str = Field(max_length=300)
    model: str = Field(default="", max_length=200)
    api_key_env: str = Field(default="", max_length=64)
    reasoning_effort: str = Field(default="", max_length=10)
    temperature: float
    max_tokens: int
    context_limit: int
    timeout_seconds: float
    embedding_model: str = Field(default="", max_length=200)

    def to_config(self) -> LLMConfig:
        return LLMConfig(**self.model_dump(include=set(ConfigIn.model_fields)))


class ApplyIn(ConfigIn):
    api_key: str | None = Field(default=None, max_length=500)
    clear_key: bool = False


class TestIn(ConfigIn):
    api_key: str | None = Field(default=None, max_length=500)


def _state(c: ContainerDep) -> dict[str, object]:
    return {
        "config": asdict(c.ai.config),
        "source": c.ai.source,  # "app" (saved here) or "env" (from .env)
        "key_source": c.ai.key_source,  # session | env | none — never the key itself
        "presets": PRESETS,
        "local_only": not c.settings.llm_allow_remote,
        "active": {"provider": c.ai.name, "model": c.ai.detect_model() or c.ai.model},
    }


@router.get("/config")
def get_config(c: ContainerDep) -> dict[str, object]:
    return _state(c)


@router.put("/config")
def apply_config(body: ApplyIn, c: ContainerDep) -> dict[str, object]:
    c.ai.apply(body.to_config(), api_key=body.api_key, clear_key=body.clear_key)
    return _state(c)


@router.post("/test")
def test_config(body: TestIn, c: ContainerDep) -> dict[str, object]:
    return asdict(c.ai.test(body.to_config(), api_key=body.api_key))


@router.get("/status")
def ai_status(c: ContainerDep) -> dict[str, object]:
    enabled = c.ai.name != "none"
    return {
        "enabled": enabled,
        "provider": c.ai.name,
        "model": c.ai.model,
        "reachable": c.ai.reachable() if enabled else False,
        "local_only": not c.settings.llm_allow_remote,
    }
