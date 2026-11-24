from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container, build_container
from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from ppos_api.main import create_app

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
    with TestClient(create_app(settings, clock)) as c:
        yield c
