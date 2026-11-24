"""Workspace settings use cases (cached; settings change rarely)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo

from ppos.application.ports import UnitOfWorkFactory
from ppos.domain.settings import WorkspaceSettings


class SettingsService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow = uow_factory
        self._cache: WorkspaceSettings | None = None

    def get(self) -> WorkspaceSettings:
        if self._cache is None:
            with self._uow() as uow:
                stored = uow.settings.all()
            self._cache = WorkspaceSettings().merged(stored) if stored else WorkspaceSettings()
        return self._cache

    def update(self, changes: Mapping[str, Any]) -> WorkspaceSettings:
        updated = self.get().merged(dict(changes))  # validates
        with self._uow() as uow:
            uow.settings.set_many(updated.to_dict())
            uow.audit.record("settings", "workspace", "update", details=dict(changes))
            uow.commit()
        self._cache = updated
        return updated

    def tz(self) -> ZoneInfo:
        return self.get().tz
