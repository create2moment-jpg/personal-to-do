"""Settings and the private-data boundary.

All private runtime data lives under ``LOCAL_DATA_DIR`` (default
``~/PersonalProductivityData``), which must be *outside* the source repository.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ppos.shared.errors import DataBoundaryError

# packages/ppos/infrastructure/config.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MIGRATIONS_DIR = REPO_ROOT / "migrations"

DATA_SUBDIRS = (
    "db",
    "notes",
    "documents",
    "indexes",
    "cache",
    "ai",
    "backups",
    "config",
    "exports",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PPOS_", env_file=".env", extra="ignore")

    local_data_dir: Path = Field(default_factory=lambda: Path.home() / "PersonalProductivityData")
    host: str = "127.0.0.1"
    port: int = 8765
    default_capacity_minutes: int = 360
    note_snapshot_interval_seconds: int = 120
    auto_migrate: bool = False
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR
    web_dist_dir: Path = REPO_ROOT / "apps" / "web" / "dist"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    log_level: str = "INFO"
    # Local AI (Phase 5 slice). Off unless a provider and model are set.
    llm_provider: str = "none"  # none | ollama | openai_compatible
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 120
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1200
    llm_allow_remote: bool = False  # never send private data off-machine by default
    prompts_dir: Path = REPO_ROOT / "prompts"
    # Escape hatch for unusual layouts; never enable for real personal data.
    allow_data_dir_in_repo: bool = False

    @field_validator("local_data_dir", mode="after")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def db_path(self) -> Path:
        return self.local_data_dir / "db" / "ppos.sqlite3"

    @property
    def backups_dir(self) -> Path:
        return self.local_data_dir / "backups"


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def enforce_data_boundary(settings: Settings, repo_root: Path = REPO_ROOT) -> None:
    """Refuse to run with private data inside (or containing) the repository."""
    data_dir = settings.local_data_dir
    if settings.allow_data_dir_in_repo:
        return
    if is_inside(data_dir, repo_root):
        raise DataBoundaryError(
            f"LOCAL_DATA_DIR {data_dir} is inside the source repository {repo_root}. "
            "Private data must live outside Git; set PPOS_LOCAL_DATA_DIR elsewhere."
        )
    if is_inside(repo_root, data_dir):
        raise DataBoundaryError(
            f"The source repository {repo_root} is inside LOCAL_DATA_DIR {data_dir}. "
            "Keep code and private data physically separate."
        )


def ensure_data_dir(settings: Settings) -> Path:
    """Create the private data layout with owner-only permissions."""
    enforce_data_boundary(settings)
    root = settings.local_data_dir
    root.mkdir(parents=True, exist_ok=True)
    for sub in DATA_SUBDIRS:
        (root / sub).mkdir(exist_ok=True)
    if os.name == "posix":
        for path in (root, *(root / s for s in DATA_SUBDIRS)):
            path.chmod(stat.S_IRWXU)  # 0o700: least privilege
    marker = root / "README.txt"
    if not marker.exists():
        marker.write_text(
            "Private data for Personal Productivity & AI OS.\n"
            "Do NOT place this directory inside a Git repository.\n"
            "Back up with `ppos backup`; restore with `ppos restore`.\n",
            encoding="utf-8",
        )
    return root
