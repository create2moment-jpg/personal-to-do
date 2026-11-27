"""The per-install API token (threat model T4/T5)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from ppos.infrastructure.config import Settings


def token_path(settings: Settings) -> Path:
    return settings.local_data_dir / "config" / "api_token"


def load_or_create_token(settings: Settings) -> str:
    """PPOS_API_TOKEN if set, else a random token in a 0600 file inside the data folder."""
    if settings.api_token:
        return settings.api_token
    path = token_path(settings)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")
    return value
