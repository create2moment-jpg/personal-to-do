from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container, build_container
from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from ppos_api.main import create_app

# Unix permission bits; Windows protects the user profile with ACLs instead.
POSIX_MODES = os.name == "posix"

# Tuesday 2026-11-24 09:00 UTC
NOW = datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(local_data_dir=tmp_path / "data", web_dist_dir=tmp_path / "no-web")


@pytest.fixture
def container(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock)


@pytest.fixture
def client(settings: Settings, clock: FixedClock) -> Iterator[TestClient]:
    app = create_app(settings, clock)
    with TestClient(
        app,
        base_url="http://127.0.0.1",
        headers={"Authorization": f"Bearer {app.state.api_token}"},
    ) as c:
        yield c


def latest_schema_version() -> int:
    from ppos.infrastructure.config import DEFAULT_MIGRATIONS_DIR
    from ppos.infrastructure.migrations import discover

    return len(discover(DEFAULT_MIGRATIONS_DIR))
